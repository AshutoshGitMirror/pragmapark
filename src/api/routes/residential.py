import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.database import (
    get_db,
    User,
    ParkingLot,
    MicroSlot,
    ResidentProfile,
    ShareListing,
    ShareBooking,
)
from src.api.auth import get_current_user
from src.api.utils import driver_id
from src.api.schemas.residential import (
    ResidentProfileCreate,
    ResidentProfileResponse,
    ResidentSlotInfo,
    ResidentialMapSlot,
    ShareListingCreate,
    ShareListingResponse,
    ShareBookingCreate,
    ShareBookingResponse,
    VehicleRegistrationRequest,
)
from src.micro.resident_map import slot_resident_mapping
from src.residential.geo import slot_geo, predict_availability
from src.pipeline.orchestrator import pipeline
from src.constants import (
    SHARE_LISTING_ACTIVE,
    SHARE_LISTING_BOOKED,
    SHARE_LISTING_CANCELLED,
    SHARE_BOOKING_ACTIVE,
    SHARE_BOOKING_COMPLETED,
    SHARE_BOOKING_CANCELLED,
    PERMIT_RATES,
    SHARE_PLATFORM_FEE,
    TX_ACTION_SHARE_BOOKING,
    TX_ACTION_SHARE_SETTLEMENT,
    TX_ACTION_SHARE_CANCELLATION,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/residential", tags=["Residential"])


def _resolve_user(session, token: dict) -> User:
    did = driver_id(token)
    u = session.query(User).filter(User.email == did).first()
    if not u:
        raise HTTPException(401, "User not found")
    return u


def _resolve_slot(session, lot_id: str, slot_index: int) -> MicroSlot:
    s = (
        session.query(MicroSlot)
        .filter(
            MicroSlot.lot_id == lot_id,
            MicroSlot.slot_index == slot_index,
            MicroSlot.active == 1,
        )
        .first()
    )
    if not s:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Slot {lot_id}/{slot_index} not found or inactive",
        )
    return s


# ─── Map ───────────────────────────────────────────────────────────────────


@router.get("/map", response_model=list[ResidentialMapSlot])
def residential_map(
    session=Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """All residential slots placed on the map: standalone home slots
    (lot_id IS NULL) plus lot-attached permitted slots. Each carries its
    own coordinates, a geohash spatial_id, and share status so the admin
    map can layer residential supply over commercial lots."""
    _resolve_user(session, user)

    slots = (
        session.query(MicroSlot)
        .filter((MicroSlot.lot_id.is_(None)) | (MicroSlot.active == 1))
        .all()
    )
    if not slots:
        return []
    slot_ids = [s.id for s in slots]

    profiles = {
        p.slot_id: p
        for p in session.query(ResidentProfile)
        .filter(
            ResidentProfile.slot_id.in_(slot_ids),
            ResidentProfile.is_active == True,
        )
        .all()
    }
    # Keep standalone slots (no commercial lot) and lot-attached permitted slots.
    relevant = [s for s in slots if s.lot_id is None or s.id in profiles]
    if not relevant:
        return []

    listings = {
        l.slot_id: l
        for l in session.query(ShareListing)
        .filter(ShareListing.slot_id.in_([s.id for s in relevant]))
        .all()
    }
    profile_ids = list({p.id for p in profiles.values()})
    owners = {
        u.id: u
        for u in session.query(User)
        .filter(User.id.in_([p.user_id for p in profiles.values()]))
        .all()
    }

    out: list[ResidentialMapSlot] = []
    for s in relevant:
        if s.latitude is None or s.longitude is None:
            continue
        prof = profiles.get(s.id)
        geo = slot_geo(float(s.latitude), float(s.longitude))
        listing = listings.get(s.id)
        resident_name = None
        if listing and prof is not None:
            owner = owners.get(prof.user_id)
            if owner:
                resident_name = owner.full_name or owner.email
        out.append(
            ResidentialMapSlot(
                slot_id=s.id,
                lot_id=s.lot_id,
                slot_index=s.slot_index,
                latitude=float(s.latitude),
                longitude=float(s.longitude),
                spatial_id=geo["spatial_id"],  # type: ignore[arg-type]
                is_shared=listing is not None
                and listing.status == SHARE_LISTING_ACTIVE,
                has_permit=prof is not None,
                permit_type=prof.permit_type if prof else None,
                price_per_hour=(
                    float(listing.price_per_hour) if listing else None
                ),
                available_from=listing.available_from if listing else None,
                available_until=listing.available_until if listing else None,
                resident_name=resident_name,
            )
        )
    return out


# ─── Permits ──────────────────────────────────────────────────────────────


@router.post("/permits", response_model=ResidentProfileResponse, status_code=201)
def create_permit(
    body: ResidentProfileCreate,
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    slot = _resolve_slot(session, body.lot_id, body.slot_index)
    if body.monthly_rate is None:
        body.monthly_rate = PERMIT_RATES.get(body.permit_type, 50.0)

    if body.end_date <= body.start_date:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "end_date must be after start_date"
        )

    existing = (
        session.query(ResidentProfile)
        .filter(ResidentProfile.slot_id == slot.id)
        .first()
    )
    if existing and existing.is_active:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Slot already has an active permit"
        )
    if existing and not existing.is_active:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A deactivated permit exists for this slot. Reactivate the existing permit instead."
        )

    try:
        profile = ResidentProfile(
            user_id=db_user.id,
            slot_id=slot.id,
            permit_type=body.permit_type,
            start_date=body.start_date,
            end_date=body.end_date,
            monthly_rate=Decimal(str(body.monthly_rate)),
            registered_vehicle=body.registered_vehicle,
        )
        session.add(profile)
        session.commit()
        slot_resident_mapping.register(
            slot_id=slot.id,
            lot_id=slot.lot_id,
            slot_index=slot.slot_index,
            user_id=db_user.id,
            registered_vehicle=body.registered_vehicle,
            is_shared=False,
            profile_id=profile.id,
        )
        session.refresh(profile)

        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == slot.lot_id).first()
        return ResidentProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            user_email=db_user.email,
            lot_id=slot.lot_id,
            lot_name=lot.name if lot else "",
            slot_index=slot.slot_index,
            permit_type=profile.permit_type,
            start_date=profile.start_date,
            end_date=profile.end_date,
            monthly_rate=float(profile.monthly_rate),
            auto_renew=bool(profile.auto_renew),
            is_active=bool(profile.is_active),
            registered_vehicle=profile.registered_vehicle,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("event=residential.permit.create.failed driver=%s lot=%s", db_user.email, body.lot_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Permit creation failed")


@router.get("/permits", response_model=list[ResidentProfileResponse])
def list_permits(
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    profiles = (
        session.query(ResidentProfile)
        .filter(ResidentProfile.user_id == db_user.id)
        .all()
    )
    if not profiles:
        return []
    slot_ids = [p.slot_id for p in profiles]
    slots = {
        s.id: s
        for s in session.query(MicroSlot)
        .filter(MicroSlot.id.in_(slot_ids))
        .all()
    }
    lot_ids = list({s.lot_id for s in slots.values()})
    lots = {
        lot.lot_id: lot
        for lot in session.query(ParkingLot)
        .filter(ParkingLot.lot_id.in_(lot_ids))
        .all()
    }
    return [
        ResidentProfileResponse(
            id=p.id,
            user_id=p.user_id,
            user_email=db_user.email,
            lot_id=slots[p.slot_id].lot_id if p.slot_id in slots else "",
            lot_name=lots[slots[p.slot_id].lot_id].name
            if p.slot_id in slots and slots[p.slot_id].lot_id in lots
            else "",
            slot_index=slots[p.slot_id].slot_index if p.slot_id in slots else 0,
            permit_type=p.permit_type,
            start_date=p.start_date,
            end_date=p.end_date,
            monthly_rate=float(p.monthly_rate),
            auto_renew=bool(p.auto_renew),
            is_active=bool(p.is_active),
            registered_vehicle=p.registered_vehicle,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in profiles
    ]


@router.get("/permits/{lot_id}/slots", response_model=list[ResidentSlotInfo])
def list_permit_slots(
    lot_id: str = Path(...),
    session=Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _resolve_user(session, user)
    slots_in_lot = (
        session.query(MicroSlot)
        .filter(MicroSlot.lot_id == lot_id, MicroSlot.active == 1)
        .all()
    )
    if not slots_in_lot:
        return []
    slot_ids = [s.id for s in slots_in_lot]
    slot_map = {s.id: s.slot_index for s in slots_in_lot}
    profiles = (
        session.query(ResidentProfile)
        .filter(
            ResidentProfile.slot_id.in_(slot_ids),
            ResidentProfile.is_active == True,
        )
        .all()
    )
    return [
        ResidentSlotInfo(
            slot_index=slot_map[p.slot_id],
            permit_type=p.permit_type,
            is_active=bool(p.is_active),
            registered_vehicle=p.registered_vehicle,
        )
        for p in profiles
    ]


# ─── Shares ────────────────────────────────────────────────────────────────


@router.post("/shares", response_model=ShareListingResponse, status_code=201)
def create_share(
    body: ShareListingCreate,
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)

    if body.resident_profile_id:
        profile = (
            session.query(ResidentProfile)
            .filter(
                ResidentProfile.id == body.resident_profile_id,
                ResidentProfile.user_id == db_user.id,
                ResidentProfile.is_active == True,
            )
            .first()
        )
        if not profile:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Resident profile not found"
            )
        slot = (
            session.query(MicroSlot)
            .filter(MicroSlot.id == profile.slot_id, MicroSlot.active == 1)
            .first()
        )
        if not slot:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Permitted slot not found or inactive"
            )
    elif body.lot_id is not None and body.slot_index is not None:
        slot = _resolve_slot(session, body.lot_id, body.slot_index)
        profile = (
            session.query(ResidentProfile)
            .filter(
                ResidentProfile.slot_id == slot.id,
                ResidentProfile.user_id == db_user.id,
                ResidentProfile.is_active == True,
            )
            .first()
        )
        if not profile:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "No active permit for this slot"
            )
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide resident_profile_id or lot_id+slot_index",
        )

    existing = (
        session.query(ShareListing)
        .filter(
            ShareListing.slot_id == slot.id,
            ShareListing.status == SHARE_LISTING_ACTIVE,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An active share listing already exists for this slot",
        )

    try:
        listing = ShareListing(
            resident_profile_id=profile.id,
            slot_id=slot.id,
            price_per_hour=Decimal(str(body.price_per_hour)),
            available_from=body.available_from,
            available_until=body.available_until,
            max_advance_days=body.max_advance_days,
        )
        session.add(listing)
        session.commit()
        slot_resident_mapping.set_shared(slot.id, True)
        session.refresh(listing)

        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == slot.lot_id).first()
        return ShareListingResponse(
            id=listing.id,
            resident_profile_id=listing.resident_profile_id,
            resident_name=db_user.full_name or db_user.email,
            lot_id=slot.lot_id,
            lot_name=lot.name if lot else "",
            slot_index=slot.slot_index,
            price_per_hour=float(listing.price_per_hour),
            available_from=listing.available_from,
            available_until=listing.available_until,
            status=listing.status,
            max_advance_days=listing.max_advance_days,
            registered_vehicle=profile.registered_vehicle,
            created_at=listing.created_at,
            updated_at=listing.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("event=residential.share.create.failed driver=%s slot=%d", db_user.email, slot.id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Share listing creation failed")


@router.get("/shares", response_model=list[ShareListingResponse])
def browse_shares(
    session=Depends(get_db),
    user: dict = Depends(get_current_user),
):
    listings = (
        session.query(ShareListing)
        .filter(ShareListing.status == SHARE_LISTING_ACTIVE)
        .all()
    )
    if not listings:
        return []
    slot_ids = list({l.slot_id for l in listings})
    profile_ids = list({l.resident_profile_id for l in listings})
    slots = {
        s.id: s
        for s in session.query(MicroSlot)
        .filter(MicroSlot.id.in_(slot_ids))
        .all()
    }
    lot_ids = list({s.lot_id for s in slots.values()})
    lots = {
        lot.lot_id: lot
        for lot in session.query(ParkingLot)
        .filter(ParkingLot.lot_id.in_(lot_ids))
        .all()
    }
    profiles = {
        p.id: p
        for p in session.query(ResidentProfile)
        .filter(ResidentProfile.id.in_(profile_ids))
        .all()
    }
    user_ids = list({p.user_id for p in profiles.values()})
    owners = {
        u.id: u
        for u in session.query(User).filter(User.id.in_(user_ids)).all()
    }
    return [
        ShareListingResponse(
            id=l.id,
            resident_profile_id=l.resident_profile_id,
            resident_name=(
                owners[profiles[l.resident_profile_id].user_id].full_name
                or owners[profiles[l.resident_profile_id].user_id].email
            )
            if l.resident_profile_id in profiles
            and profiles[l.resident_profile_id].user_id in owners
            else "",
            lot_id=slots[l.slot_id].lot_id if l.slot_id in slots else "",
            lot_name=lots[slots[l.slot_id].lot_id].name
            if l.slot_id in slots and slots[l.slot_id].lot_id in lots
            else "",
            slot_index=slots[l.slot_id].slot_index if l.slot_id in slots else 0,
            price_per_hour=float(l.price_per_hour),
            available_from=l.available_from,
            available_until=l.available_until,
            status=l.status,
            max_advance_days=l.max_advance_days,
            registered_vehicle=profiles[l.resident_profile_id].registered_vehicle
            if l.resident_profile_id in profiles
            else None,
            created_at=l.created_at,
            updated_at=l.updated_at,
        )
        for l in listings
    ]


@router.get("/shares/bookings", response_model=list[ShareBookingResponse])
def list_share_bookings(
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    bookings = (
        session.query(ShareBooking)
        .filter(ShareBooking.driver_id == db_user.email)
        .order_by(ShareBooking.created_at.desc())
        .all()
    )
    if not bookings:
        return []
    listing_ids = list({b.share_listing_id for b in bookings})
    listings = {
        l.id: l
        for l in session.query(ShareListing).filter(ShareListing.id.in_(listing_ids)).all()
    }
    slot_ids = list({l.slot_id for l in listings.values()})
    slots = {
        s.id: s
        for s in session.query(MicroSlot).filter(MicroSlot.id.in_(slot_ids)).all()
    }
    lot_ids = list({s.lot_id for s in slots.values()})
    lots = {
        lot.lot_id: lot
        for lot in session.query(ParkingLot).filter(ParkingLot.lot_id.in_(lot_ids)).all()
    }
    return [
        ShareBookingResponse(
            id=b.id,
            share_listing_id=b.share_listing_id,
            slot_id=listings[b.share_listing_id].slot_id if b.share_listing_id in listings else 0,
            driver_name=db_user.full_name or db_user.email,
            lot_name=lots[slots[listings[b.share_listing_id].slot_id].lot_id].name
            if b.share_listing_id in listings
            and listings[b.share_listing_id].slot_id in slots
            and slots[listings[b.share_listing_id].slot_id].lot_id in lots
            else "",
            slot_index=slots[listings[b.share_listing_id].slot_id].slot_index
            if b.share_listing_id in listings
            and listings[b.share_listing_id].slot_id in slots
            else 0,
            start_time=b.start_time,
            end_time=b.end_time,
            total_cost=float(b.total_cost),
            platform_fee=float(b.platform_fee),
            owner_payout=float(b.owner_payout),
            status=b.status,
            vehicle_id=b.vehicle_id,
            blockchain_ref=None,
            created_at=b.created_at,
        )
        for b in bookings
    ]


def _utc_dt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/shares/book", response_model=ShareBookingResponse, status_code=201)
def book_share(
    body: ShareBookingCreate,
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)

    listing = (
        session.query(ShareListing)
        .filter(
            ShareListing.id == body.share_listing_id,
            ShareListing.status == SHARE_LISTING_ACTIVE,
        )
        .first()
    )
    if not listing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Share listing not found or not available"
        )

    start = _utc_dt(body.start_time)
    end = _utc_dt(body.end_time)
    now = datetime.now(timezone.utc)

    if start >= end:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "start_time must be before end_time"
        )
    if start < now:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "start_time must be in the future"
        )
    if (start - now).total_seconds() > listing.max_advance_days * 86400:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Booking cannot be more than {listing.max_advance_days} days in advance",
        )

    try:
        from_hr, from_min = (
            int(listing.available_from[:2]),
            int(listing.available_from[3:]),
        )
        until_hr, until_min = (
            int(listing.available_until[:2]),
            int(listing.available_until[3:]),
        )
    except (ValueError, IndexError):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Invalid listing time configuration",
        )
    start_mins = start.hour * 60 + start.minute
    end_mins = end.hour * 60 + end.minute
    from_mins = from_hr * 60 + from_min
    until_mins = until_hr * 60 + until_min
    bstart = start_mins
    bend = end_mins
    overnight = False
    if from_mins >= until_mins:
        until_mins += 1440
        overnight = True
    if overnight:
        if bstart < from_mins:
            bstart += 1440
            bend += 1440
        elif bend < start_mins:
            bend += 1440
    if bstart < from_mins or bend > until_mins:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Booking must be within {listing.available_from}-{listing.available_until}",
        )

    overlap = (
        session.query(ShareBooking)
        .join(ShareListing, ShareBooking.share_listing_id == ShareListing.id)
        .filter(
            ShareListing.slot_id == listing.slot_id,
            ShareBooking.status == SHARE_BOOKING_ACTIVE,
            ShareBooking.start_time < end,
            ShareBooking.end_time > start,
        )
        .first()
    )
    if overlap:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Booking time conflicts with existing booking"
        )

    duration_h = (end - start).total_seconds() / 3600
    total_cost = round(duration_h * float(listing.price_per_hour), 2)
    platform_fee = round(total_cost * SHARE_PLATFORM_FEE, 2)
    owner_payout = round(total_cost - platform_fee, 2)

    profile = (
        session.query(ResidentProfile)
        .filter(ResidentProfile.slot_id == listing.slot_id)
        .first()
    )

    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)
    try:
        booking = ShareBooking(
            share_listing_id=listing.id,
            driver_id=db_user.email,
            start_time=start_naive,
            end_time=end_naive,
            total_cost=Decimal(str(total_cost)),
            platform_fee=Decimal(str(platform_fee)),
            owner_payout=Decimal(str(owner_payout)),
            vehicle_id=profile.registered_vehicle if profile else None,
        )
        session.add(booking)

        listing.status = SHARE_LISTING_BOOKED
        session.commit()
        session.refresh(booking)

        _cid = None
        try:
            _cid = pipeline.ipfs.pin({
                "type": "share_booking",
                "booking_id": booking.id,
                "share_listing_id": booking.share_listing_id,
                "driver_id": booking.driver_id,
                "slot_id": listing.slot_id,
                "start_time": start_naive.isoformat(),
                "end_time": end_naive.isoformat(),
                "total_cost": total_cost,
                "platform_fee": platform_fee,
                "owner_payout": owner_payout,
                "vehicle_id": booking.vehicle_id,
            }, content_type="share_booking")
            pipeline.share_settlement_contract.execute({
                "action": "create", "booking_id": booking.id,
            })
            pipeline.ledger.add_transaction({
                "type": "share_booking", "booking_id": booking.id,
                "share_listing_id": booking.share_listing_id,
                "driver_id": booking.driver_id,
                "action": TX_ACTION_SHARE_BOOKING,
                "amount": total_cost,
                "platform_fee": platform_fee,
                "owner_payout": owner_payout,
                "ipfs_cid": _cid,
            })
        except Exception:
            logger.exception("event=residential.share.book.blockchain_failed booking=%d", booking.id)

        slot = session.query(MicroSlot).filter(MicroSlot.id == listing.slot_id).first()
        lot = (
            session.query(ParkingLot).filter(ParkingLot.lot_id == slot.lot_id).first()
            if slot
            else None
        )
        return ShareBookingResponse(
            id=booking.id,
            share_listing_id=booking.share_listing_id,
            slot_id=slot.id if slot else 0,
            driver_name=db_user.full_name or db_user.email,
            lot_name=lot.name if lot else "",
            slot_index=slot.slot_index if slot else 0,
            start_time=booking.start_time,
            end_time=booking.end_time,
            total_cost=float(booking.total_cost),
            platform_fee=float(booking.platform_fee),
            owner_payout=float(booking.owner_payout),
            vehicle_id=booking.vehicle_id,
            status=booking.status,
            blockchain_ref=_cid,
            created_at=booking.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("event=residential.share.book.failed driver=%s listing=%d", db_user.email, listing.id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Share booking failed")


@router.delete("/shares/{listing_id}")
def cancel_share_listing(
    listing_id: int = Path(..., ge=1),
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    listing = (
        session.query(ShareListing)
        .filter(ShareListing.id == listing_id)
        .first()
    )
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    profile = (
        session.query(ResidentProfile)
        .filter(
            ResidentProfile.id == listing.resident_profile_id,
            ResidentProfile.user_id == db_user.id,
        )
        .first()
    )
    if not profile and user.get("role") != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Not authorized to cancel this listing"
        )
    active_bookings = (
        session.query(ShareBooking)
        .filter(
            ShareBooking.share_listing_id == listing.id,
            ShareBooking.status == SHARE_BOOKING_ACTIVE,
        )
        .first()
    )
    if active_bookings:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot cancel listing with active bookings",
        )
    if listing.status == SHARE_LISTING_CANCELLED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Listing is already cancelled"
        )
    try:
        listing.status = SHARE_LISTING_CANCELLED
        session.commit()
        slot_resident_mapping.set_shared(listing.slot_id, False)
        return {"status": "cancelled", "listing_id": listing_id}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("event=residential.share.cancel.failed listing=%d", listing_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel listing")


@router.post("/shares/booking/{booking_id}/cancel")
def cancel_share_booking(
    booking_id: int = Path(..., ge=1),
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    booking = (
        session.query(ShareBooking)
        .filter(ShareBooking.id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.driver_id != db_user.email and user.get("role") != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Not authorized to cancel this booking"
        )
    if booking.status != SHARE_BOOKING_ACTIVE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only active bookings can be cancelled"
        )

    try:
        booking.status = SHARE_BOOKING_CANCELLED
        listing = (
            session.query(ShareListing)
            .filter(ShareListing.id == booking.share_listing_id)
            .first()
        )
        if listing and listing.status == SHARE_LISTING_BOOKED:
            listing.status = SHARE_LISTING_ACTIVE
        session.commit()
        try:
            _cid = pipeline.ipfs.pin({
                "type": "share_cancellation",
                "booking_id": booking.id,
                "share_listing_id": booking.share_listing_id,
                "driver_id": booking.driver_id,
                "status": "cancelled",
            }, content_type="share_cancellation")
            pipeline.share_settlement_contract.execute({
                "action": "cancel", "booking_id": booking.id,
            })
            pipeline.ledger.add_transaction({
                "type": "share_cancellation", "booking_id": booking.id,
                "share_listing_id": booking.share_listing_id,
                "driver_id": booking.driver_id,
                "action": TX_ACTION_SHARE_CANCELLATION,
                "ipfs_cid": _cid, "status": "cancelled",
            })
        except Exception:
            logger.exception("event=residential.share.booking.cancel.blockchain_failed booking=%d", booking.id)
        return {"status": "cancelled", "booking_id": booking_id}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("event=residential.share.booking.cancel.failed booking=%d driver=%s", booking_id, db_user.email)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to cancel booking")


@router.post("/shares/booking/{booking_id}/settle")
def settle_share_booking(
    booking_id: int = Path(..., ge=1),
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    booking = session.query(ShareBooking).filter(ShareBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.driver_id != db_user.email and user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
    if booking.status != SHARE_BOOKING_ACTIVE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only active bookings can be settled")
    if booking.end_time > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Booking end time has not passed yet")
    try:
        booking.status = SHARE_BOOKING_COMPLETED
        listing = session.query(ShareListing).filter(
            ShareListing.id == booking.share_listing_id
        ).first()
        if listing and listing.status == SHARE_LISTING_BOOKED:
            listing.status = SHARE_LISTING_ACTIVE
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("event=residential.share.booking.settle.db_failed booking=%d", booking_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to settle booking")
    cid = None
    try:
        platform_fee = float(booking.platform_fee)
        owner_payout = float(booking.owner_payout)
        cid = pipeline.ipfs.pin({
            "type": "share_settlement",
            "booking_id": booking.id,
            "share_listing_id": booking.share_listing_id,
            "platform_fee": platform_fee,
            "owner_payout": owner_payout,
            "settled_at": datetime.now(timezone.utc).isoformat(),
        }, content_type="share_settlement")
        pipeline.share_settlement_contract.execute({
            "action": "settle", "booking_id": booking.id,
            "platform_fee": platform_fee,
            "owner_payout": owner_payout,
        })
        pipeline.ledger.add_transaction({
            "type": "share_settlement", "booking_id": booking.id,
            "share_listing_id": booking.share_listing_id,
            "action": TX_ACTION_SHARE_SETTLEMENT,
            "platform_fee": platform_fee,
            "owner_payout": owner_payout,
            "ipfs_cid": cid,
            "driver_id": booking.driver_id,
        })
    except Exception:
        logger.exception("event=residential.share.booking.settle.blockchain_failed booking=%d", booking_id)
    return {
        "status": "completed", "booking_id": booking_id,
        "platform_fee": float(booking.platform_fee),
        "owner_payout": float(booking.owner_payout),
        "blockchain_ref": cid,
    }


@router.put("/permits/{permit_id}/vehicle", response_model=ResidentProfileResponse)
def register_vehicle(
    permit_id: int = Path(..., ge=1),
    body: VehicleRegistrationRequest = ...,
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    profile = (
        session.query(ResidentProfile)
        .filter(
            ResidentProfile.id == permit_id,
            ResidentProfile.user_id == db_user.id,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permit not found")
    if not profile.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Permit is not active")
    try:
        profile.registered_vehicle = body.vehicle_id.upper()
        session.commit()
        session.refresh(profile)
        slot = session.query(MicroSlot).filter(MicroSlot.id == profile.slot_id).first()
        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == slot.lot_id).first() if slot else None
        return ResidentProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            user_email=db_user.email,
            lot_id=lot.lot_id if lot else "",
            lot_name=lot.name if lot else "",
            slot_index=slot.slot_index if slot else 0,
            permit_type=profile.permit_type,
            start_date=profile.start_date,
            end_date=profile.end_date,
            monthly_rate=float(profile.monthly_rate),
            auto_renew=bool(profile.auto_renew),
            is_active=bool(profile.is_active),
            registered_vehicle=profile.registered_vehicle,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
    except Exception:
        session.rollback()
        logger.exception("event=residential.vehicle.register.failed permit=%d", permit_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Vehicle registration failed")


@router.delete("/permits/{permit_id}/vehicle", response_model=ResidentProfileResponse)
def unregister_vehicle(
    permit_id: int = Path(..., ge=1),
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    profile = (
        session.query(ResidentProfile)
        .filter(
            ResidentProfile.id == permit_id,
            ResidentProfile.user_id == db_user.id,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permit not found")
    if not profile.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Permit is not active")
    try:
        profile.registered_vehicle = None
        session.commit()
        session.refresh(profile)
        slot = session.query(MicroSlot).filter(MicroSlot.id == profile.slot_id).first()
        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == slot.lot_id).first() if slot else None
        return ResidentProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            user_email=db_user.email,
            lot_id=lot.lot_id if lot else "",
            lot_name=lot.name if lot else "",
            slot_index=slot.slot_index if slot else 0,
            permit_type=profile.permit_type,
            start_date=profile.start_date,
            end_date=profile.end_date,
            monthly_rate=float(profile.monthly_rate),
            auto_renew=bool(profile.auto_renew),
            is_active=bool(profile.is_active),
            registered_vehicle=profile.registered_vehicle,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
    except Exception:
        session.rollback()
        logger.exception("event=residential.vehicle.unregister.failed permit=%d", permit_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Vehicle unregistration failed")


@router.post("/permits/{permit_id}/deactivate", response_model=ResidentProfileResponse)
def deactivate_permit(
    permit_id: int = Path(..., ge=1),
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    db_user = _resolve_user(session, user)
    profile = (
        session.query(ResidentProfile)
        .filter(
            ResidentProfile.id == permit_id,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permit not found")
    if profile.user_id != db_user.id and user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to deactivate this permit")
    if not profile.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Permit is already deactivated")

    active_shares = (
        session.query(ShareListing)
        .filter(
            ShareListing.slot_id == profile.slot_id,
            ShareListing.status == SHARE_LISTING_ACTIVE,
        )
        .first()
    )
    if active_shares:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot deactivate permit with active share listings. Cancel them first.",
        )

    try:
        profile.is_active = False
        session.commit()
        slot_resident_mapping.unregister(profile.slot_id)
        session.refresh(profile)
        slot = session.query(MicroSlot).filter(MicroSlot.id == profile.slot_id).first()
        lot = session.query(ParkingLot).filter(ParkingLot.lot_id == slot.lot_id).first() if slot else None
        return ResidentProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            user_email=db_user.email,
            lot_id=lot.lot_id if lot else "",
            lot_name=lot.name if lot else "",
            slot_index=slot.slot_index if slot else 0,
            permit_type=profile.permit_type,
            start_date=profile.start_date,
            end_date=profile.end_date,
            monthly_rate=float(profile.monthly_rate),
            auto_renew=bool(profile.auto_renew),
            is_active=bool(profile.is_active),
            registered_vehicle=profile.registered_vehicle,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        logger.exception("event=residential.permit.deactivate.failed permit=%d", permit_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Permit deactivation failed")

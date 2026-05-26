import requests
import os
import zipfile
import io

RAW_DATA_PATH = "data/raw/birmingham_parking.csv"

def download_birmingham_dataset():
    """
    Download the Birmingham Parking dataset from UCI.
    This is a reliable CSV dataset with 35,000+ instances.
    """
    print("Fetching Birmingham Parking Dataset from UCI...")
    url = "https://archive.ics.uci.edu/ml/machine-learning-databases/00482/dataset.zip"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # Birmingham dataset usually has one CSV inside
                csv_filename = [f for f in z.namelist() if f.endswith('.csv')][0]
                with z.open(csv_filename) as f_in:
                    content = f_in.read()
                    with open(RAW_DATA_PATH, "wb") as f_out:
                        f_out.write(content)
            print(f"Birmingham dataset saved to {RAW_DATA_PATH}")
        else:
            print(f"Failed to download. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error during download: {e}")

if __name__ == "__main__":
    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    download_birmingham_dataset()

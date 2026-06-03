import { motion } from 'framer-motion'

interface Props {
  children: React.ReactNode
  delay?: number
  className?: string
}

const sectionVariants = {
  hidden: { opacity: 0, y: 60 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: [0.25, 0.1, 0.25, 1] },
  },
}

export function AnimatedSection({ children, delay = 0, className }: Props) {
  return (
    <motion.div
      variants={sectionVariants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-80px' }}
      transition={{ delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

/** Shared Motion presets for consistent micro-interactions. */

export const easeOut = [0.16, 1, 0.3, 1] as const;

export const pageTransition = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: 0.28, ease: easeOut },
} as const;

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 },
} as const;

export const riseIn = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: easeOut },
} as const;

export const scaleIn = {
  initial: { opacity: 0, scale: 0.96 },
  animate: { opacity: 1, scale: 1 },
  transition: { duration: 0.25, ease: easeOut },
} as const;

export const springSoft = {
  type: "spring" as const,
  stiffness: 380,
  damping: 28,
  mass: 0.8,
};

export const springSnappy = {
  type: "spring" as const,
  stiffness: 480,
  damping: 32,
};

/** Stagger children: delay = index * step */
export function staggerDelay(index: number, step = 0.04, base = 0.05) {
  return { delay: base + index * step, duration: 0.28, ease: easeOut };
}

export const listItemMotion = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, x: -8 },
  transition: { duration: 0.22, ease: easeOut },
} as const;

export const hoverLift = {
  y: -2,
  transition: springSnappy,
} as const;

export const pressScale = {
  scale: 0.98,
  transition: { duration: 0.1 },
} as const;

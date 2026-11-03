// Black and white only. Colour appears only when it measures something.
export const C = {
  ground: '#000000',
  text: '#F5F5F3',
  second: '#A3A3A0',
  third: '#8A8A87',
  line: '#2E2E2C',
  track: '#3A3A38',
  border: '#5E5E5B',
  field: '#141414',
  divided: '#FF5A3C',
  mixed: '#9A9A96',
  agreed: '#7BEBAE',
  paper: '#F5F5F3',
  ink: '#0A0A0A',
  inkSecond: '#3F3F3D',
  inkThird: '#5C5C59',
};

export const F = {
  regular: 'BricolageGrotesque_400Regular',
  medium: 'BricolageGrotesque_500Medium',
  semi: 'BricolageGrotesque_600SemiBold',
  mono: 'DMMono_400Regular',
};

export function rgba(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

// A topic's colour comes from its gap between the two sides.
export function gapColor(gap: number): string {
  if (gap < 0.3) return C.agreed;
  if (gap > 0.6) return C.divided;
  return C.mixed;
}

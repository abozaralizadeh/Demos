import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import type { DataBlock } from './api';
import type { Copy } from './copy';
import { C, F, rgba } from './theme';

export type Tone = 'dark' | 'white';

export const ink = (tone: Tone) =>
  tone === 'white'
    ? { bg: C.paper, text: C.ink, second: C.inkSecond, third: C.inkThird, ring: C.third }
    : { bg: C.ground, text: C.text, second: C.second, third: C.third, ring: C.border };

function MicIcon({ size, color, filled }: { size: number; color: string; filled?: boolean }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x={9} y={3} width={6} height={12} rx={3} stroke={color} strokeWidth={1.8} fill={filled ? color : 'none'} />
      <Path d="M5 11a7 7 0 0 0 14 0" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
      <Path d="M12 18v3" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
    </Svg>
  );
}

function useSpin(seconds: number) {
  const turn = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(turn, { toValue: 1, duration: seconds * 1000, easing: Easing.linear, useNativeDriver: true }),
    );
    loop.start();
    return () => loop.stop();
  }, [turn, seconds]);
  return turn.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
}

// The Talk tab. Big with a slow dotted ring on home screens, solid while listening.
export function Mic({
  big,
  tone = 'dark',
  outline,
  filled,
  label,
  onPress,
}: {
  big?: boolean;
  tone?: Tone;
  outline?: boolean;
  filled?: boolean;
  label: string;
  onPress: () => void;
}) {
  const t = ink(tone);
  const size = big ? 88 : 72;
  const spin = useSpin(60);
  const face = outline ? 'transparent' : t.text;
  const glyph = outline ? t.text : t.bg;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} hitSlop={8}>
      <View
        style={{
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: face,
          borderWidth: outline ? 1 : 0,
          borderColor: t.ring,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {big && !filled && (
          <Animated.View
            style={{
              pointerEvents: 'none',
              position: 'absolute',
              top: -12,
              left: -12,
              right: -12,
              bottom: -12,
              borderRadius: (size + 24) / 2,
              borderWidth: 2,
              borderStyle: 'dotted',
              borderColor: t.ring,
              transform: [{ rotate: spin }],
            }}
          />
        )}
        <MicIcon size={big ? 32 : 28} color={glyph} filled={filled} />
      </View>
    </Pressable>
  );
}

function MapIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Circle cx={8} cy={9} r={5} stroke={color} strokeWidth={1.6} />
      <Circle cx={17.5} cy={6.5} r={2.5} stroke={color} strokeWidth={1.6} />
      <Circle cx={17} cy={17.5} r={3.5} stroke={color} strokeWidth={1.6} />
    </Svg>
  );
}

function YouIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Circle cx={12} cy={12} r={9} stroke={color} strokeWidth={1.6} />
      <Circle cx={12} cy={12} r={3} fill={color} />
    </Svg>
  );
}

// Map, the mic, You. Map and You stay hidden until someone has talked once.
export function Nav({
  copy,
  tone = 'dark',
  big,
  outline,
  unlocked,
  current,
  onMap,
  onTalk,
  onYou,
}: {
  copy: Copy;
  tone?: Tone;
  big?: boolean;
  outline?: boolean;
  unlocked: boolean;
  current?: 'map' | 'you';
  onMap: () => void;
  onTalk: () => void;
  onYou: () => void;
}) {
  const t = ink(tone);
  const tab = (name: 'map' | 'you', label: string, onPress: () => void) => {
    const color = current === name ? t.text : t.second;
    return (
      <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={s.tab}>
        {name === 'map' ? <MapIcon color={color} /> : <YouIcon color={color} />}
        <Text style={[s.tabText, { color }]}>{label}</Text>
      </Pressable>
    );
  };
  return (
    <View style={s.nav}>
      <View style={s.side}>{unlocked && tab('map', copy.map, onMap)}</View>
      <Mic big={big} tone={tone} outline={outline} label={copy.talkToWorld} onPress={onTalk} />
      <View style={[s.side, { alignItems: 'flex-end' }]}>{unlocked && tab('you', copy.you, onYou)}</View>
    </View>
  );
}

export function TextLink({
  label,
  tone = 'dark',
  left,
  onPress,
}: {
  label: string;
  tone?: Tone;
  left?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={[s.link, left && { alignSelf: 'flex-start', minWidth: 0 }]}>
      <Text style={[s.linkText, { color: tone === 'white' ? C.inkThird : C.third }]}>{label}</Text>
    </Pressable>
  );
}

// Three round marks: this came from people.
export function People({ label, tone = 'dark', onPress }: { label: string; tone?: Tone; onPress?: () => void }) {
  const t = ink(tone);
  return (
    <Pressable accessibilityRole={onPress ? 'button' : undefined} disabled={!onPress} onPress={onPress} style={s.people}>
      <View style={{ flexDirection: 'row' }}>
        {[1, 0.65, 0.35].map((o, i) => (
          <View key={i} style={[s.dot, { backgroundColor: t.text, opacity: o, marginLeft: i ? -3 : 0 }]} />
        ))}
      </View>
      <Text style={[s.small, { color: t.second, flex: 1 }, onPress && s.underline]}>{label}</Text>
    </Pressable>
  );
}

// The line the person just said, small and grey above the World's answer.
export function Heard({ text, tone = 'dark' }: { text: string; tone?: Tone }) {
  const t = ink(tone);
  if (!text) return null;
  return (
    <View style={s.heard}>
      <View style={[s.heardDot, { backgroundColor: t.second }]} />
      <Text style={[s.heardText, { color: t.second }]}>{text}</Text>
    </View>
  );
}

// Square mark and mono type: this is data, not anyone's opinion.
export function Data({ block, copy, onSource }: { block: Partial<DataBlock>; copy: Copy; onSource?: () => void }) {
  return (
    <View style={s.data} accessibilityLabel={copy.dataNotOpinion}>
      <View style={s.people}>
        <View style={s.square} />
        <Text style={s.dataLabel}>{copy.dataNotOpinion}</Text>
      </View>
      {block.title ? <Text style={s.dataTitle}>{block.title}</Text> : null}
      {(block.items ?? []).map((item, i) => (
        <View key={i} style={s.dataRow}>
          <Text style={s.dataItem}>{item.label}</Text>
          <Text style={s.dataValue}>{item.value}</Text>
        </View>
      ))}
      {block.source ? (
        <Pressable accessibilityRole={onSource ? 'button' : undefined} disabled={!onSource} onPress={onSource}>
          <Text style={s.dataLabel}>
            <Text style={onSource && s.underline}>
              {copy.source}: {block.source}
            </Text>
            {block.placeholder ? `\n${copy.placeholderFact}` : ''}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

// A topic is two circles. Further apart means more divided.
export function Lobes({ size, color, overlap, drift }: { size: number; color: string; overlap: number; drift?: boolean }) {
  const move = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!drift) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(move, { toValue: 1, duration: 3000, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(move, { toValue: 0, duration: 3000, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [drift, move]);
  const right = move.interpolate({ inputRange: [0, 1], outputRange: [0, 9] });
  const left = move.interpolate({ inputRange: [0, 1], outputRange: [0, -9] });
  const lobe = { width: size, height: size, borderRadius: size / 2, backgroundColor: rgba(color, 0.32) };
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'center' }} accessible={false}>
      <Animated.View style={[lobe, { transform: [{ translateX: right }] }]} />
      <Animated.View style={[lobe, { marginLeft: -overlap, transform: [{ translateX: left }] }]} />
    </View>
  );
}

// The listening dome: rings of dots that pulse outward while someone talks.
export function Dome({ active }: { active: boolean }) {
  const { width } = useWindowDimensions();
  const scale = width / 390;
  const rings = useRef(Array.from({ length: 8 }, () => new Animated.Value(0))).current;
  const dots = useMemo(() => {
    let seed = 7;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return seed / 2147483647;
    };
    const out: { x: number; y: number; s: number; ring: number }[] = [];
    for (let ring = 0; ring < 8; ring++) {
      const radius = 72 + ring * 26;
      const count = 14 + ring * 5;
      for (let i = 0; i < count; i++) {
        const angle = Math.PI * (1 + (i + 0.5) / count);
        const r = radius + (rand() - 0.5) * 12;
        const size = 3 + Math.round(rand() * 2);
        const x = Math.round(195 + Math.cos(angle) * r);
        const y = Math.round(264 + Math.sin(angle) * r);
        if (x < 2 || x > 384 || y < 2) continue;
        out.push({ x: x * scale, y: y * scale, s: size, ring });
      }
    }
    return out;
  }, [scale]);

  useEffect(() => {
    if (!active) return;
    const loops = rings.map((v, ring) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(ring * 160),
          Animated.timing(v, { toValue: 1, duration: 1100, easing: Easing.out(Easing.quad), useNativeDriver: true }),
          Animated.timing(v, { toValue: 0, duration: 1700 - ring * 160 + 160, easing: Easing.in(Easing.quad), useNativeDriver: true }),
        ]),
      ),
    );
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [active, rings]);

  return (
    <View style={[s.dome, { height: 380 * scale }]}>
      {dots.map((d, i) => {
        const v = rings[d.ring];
        return (
          <Animated.View
            key={i}
            style={{
              position: 'absolute',
              left: d.x,
              top: d.y,
              width: d.s,
              height: d.s,
              borderRadius: d.s / 2,
              backgroundColor: C.text,
              opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.14, 0.95] }),
              transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [1, 1.6] }) }],
            }}
          />
        );
      })}
    </View>
  );
}

// Every number in this build is sample data, so every screen says so.
export function SampleTag({ label, tone = 'dark' }: { label: string; tone?: Tone }) {
  const t = ink(tone);
  return (
    <View style={[s.sample, { borderColor: t.second }]}>
      <Text style={[s.sampleText, { color: t.second }]}>{label}</Text>
    </View>
  );
}

export const s = StyleSheet.create({
  underline: { textDecorationLine: 'underline' },
  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 28 },
  side: { flex: 1 },
  tab: { width: 56, height: 64, alignItems: 'center', justifyContent: 'center', gap: 6 },
  tabText: { fontFamily: F.regular, fontSize: 13 },
  link: { alignSelf: 'center', height: 44, minWidth: 120, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  linkText: { fontFamily: F.regular, fontSize: 13 },
  people: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  small: { fontFamily: F.regular, fontSize: 14, lineHeight: 18 },
  heard: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  heardDot: { width: 8, height: 8, borderRadius: 4, marginTop: 7 },
  heardText: { flex: 1, fontFamily: F.regular, fontSize: 17, lineHeight: 22 },
  data: { gap: 14, paddingTop: 18, paddingBottom: 10, borderTopWidth: 1, borderBottomWidth: 1, borderColor: C.border },
  square: { width: 10, height: 10, backgroundColor: C.text },
  dataLabel: { fontFamily: F.mono, fontSize: 13, lineHeight: 18, color: C.second },
  dataTitle: { fontFamily: F.mono, fontSize: 15, color: C.text },
  dataRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 },
  dataItem: { flex: 1, fontFamily: F.mono, fontSize: 15, color: C.text },
  dataValue: { fontFamily: F.mono, fontSize: 30, letterSpacing: -0.9, color: C.text },
  dome: { pointerEvents: 'none', position: 'absolute', left: 0, right: 0, bottom: 0, overflow: 'hidden' },
  sample: { alignSelf: 'flex-start', borderWidth: 1, paddingHorizontal: 8, paddingVertical: 3 },
  sampleText: { fontFamily: F.mono, fontSize: 11, letterSpacing: 0.4 },
});

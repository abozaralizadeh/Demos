import { useEffect, useRef } from 'react';
import { Animated, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { DevCheck, Fact, Open } from './api';
import { fill, type Copy } from './copy';
import { C, F } from './theme';
import { Lobes, Mic, Nav, People, SampleTag, TextLink } from './ui';

function Rise({ delay, children }: { delay: number; children: React.ReactNode }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, { toValue: 1, duration: 900, delay, useNativeDriver: true }).start();
  }, [v, delay]);
  const y = v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] });
  return <Animated.View style={{ opacity: v, transform: [{ translateY: y }] }}>{children}</Animated.View>;
}

function TwoDots() {
  return (
    <View style={{ flexDirection: 'row' }}>
      <View style={[sc.logoDot]} />
      <View style={[sc.logoDot, { marginLeft: -9 }]} />
    </View>
  );
}

export function Verify({
  copy,
  busy,
  onVerify,
}: {
  copy: Copy;
  busy: boolean;
  onVerify: (as?: DevCheck) => void;
}) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[sc.screen, { paddingTop: insets.top + 40, paddingBottom: insets.bottom + 24 }]}>
      <View style={sc.brand}>
        <TwoDots />
        <Text style={sc.brandText}>Demos</Text>
      </View>
      <View style={{ gap: 32 }}>
        <View style={{ gap: 16 }}>
          <Text style={sc.h1}>{copy.verifyTitle}</Text>
          <Text style={sc.sub}>{copy.verifySub}</Text>
        </View>
        <Pressable accessibilityRole="button" onPress={() => onVerify()} disabled={busy} style={[sc.button, busy && { opacity: 0.5 }]}>
          <Text style={sc.buttonText}>{copy.verify}</Text>
        </Pressable>
        <View>
          <Text style={sc.dev}>{copy.devNote}</Text>
          {/* Only while the dev stub stands in for SPID and CIE, so the error screens can be reached. */}
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 20 }}>
            <TextLink label={copy.devMinor} onPress={() => onVerify('minor')} />
            <TextLink label={copy.devBroken} onPress={() => onVerify('broken')} />
          </View>
        </View>
      </View>
    </View>
  );
}

// Every error case gets a whole screen: what happened, in plain words, and what to do next.
export function Problem({
  title,
  body,
  action,
  onAction,
  other,
  onOther,
}: {
  title: string;
  body: string;
  action?: string;
  onAction?: () => void;
  other?: string;
  onOther?: () => void;
}) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[sc.screen, { paddingTop: insets.top + 40, paddingBottom: insets.bottom + 32 }]}>
      <View style={sc.brand}>
        <TwoDots />
        <Text style={sc.brandText}>Demos</Text>
      </View>
      <View style={{ gap: 32 }}>
        <View style={{ gap: 16 }}>
          <Text style={sc.h1}>{title}</Text>
          <Text style={sc.sub}>{body}</Text>
        </View>
        {action && onAction && (
          <Pressable accessibilityRole="button" onPress={onAction} style={sc.button}>
            <Text style={sc.buttonText}>{action}</Text>
          </Pressable>
        )}
        {other && onOther && <TextLink label={other} onPress={onOther} />}
      </View>
    </View>
  );
}

// Asked before the system prompt, so people know what they'd be saying yes to.
export function NotifyAsk({ copy, onYes, onNo }: { copy: Copy; onYes: () => void; onNo: () => void }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[sc.screen, { paddingTop: insets.top + 40, paddingBottom: insets.bottom + 32 }]}>
      <Text style={sc.sub}>{copy.notifications}</Text>
      <View style={{ gap: 28 }}>
        <Text style={sc.h1}>{copy.notifyTitle}</Text>
        {copy.notifyBody.map((line, i) => (
          <Text key={i} style={[sc.h2, { fontSize: 24, lineHeight: 29 }, i > 0 && { color: C.second }]}>
            {line}
          </Text>
        ))}
        <Pressable accessibilityRole="button" onPress={onYes} style={sc.button}>
          <Text style={sc.buttonText}>{copy.notifyYes}</Text>
        </Pressable>
        <TextLink label={copy.notNow} onPress={onNo} />
      </View>
    </View>
  );
}

// Square marks are data, so a fact's source sits in a square-cornered block like the fact did.
export function SourceScreen({
  copy,
  fact,
  base,
  onBack,
}: {
  copy: Copy;
  fact: Fact | null;
  base: number | null;
  onBack: () => void;
}) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[sc.full, { paddingTop: insets.top, paddingBottom: insets.bottom + 16 }]}>
      <ScrollView contentContainerStyle={[sc.main, { paddingTop: 32, gap: 28 }]}>
        <TextLink label={`‹ ${copy.back}`} onPress={onBack} left />
        {fact ? (
          <>
            <Text style={sc.sub}>{copy.sourceTitle}</Text>
            <Text style={sc.h2}>{fact.title}</Text>
            <View style={sc.block}>
              {fact.items.map((it) => (
                <View key={it.label} style={sc.blockRow}>
                  <Text style={sc.mono}>{it.label}</Text>
                  <Text style={[sc.mono, { color: C.text }]}>{it.value}</Text>
                </View>
              ))}
              <View style={sc.rule} />
              {[
                [copy.source, fact.source_name],
                [copy.sourceYear, fact.year],
                [copy.sourceCheck, fact.reviewed ? copy.checkedYes : copy.checkedNo],
                ...(fact.review_due ? [[copy.nextCheck, fact.review_due]] : []),
              ].map(([k, v]) => (
                <View key={k} style={sc.blockRow}>
                  <Text style={sc.mono}>{k}</Text>
                  <Text style={[sc.mono, { color: C.text, flexShrink: 1, textAlign: 'right' }]}>{v}</Text>
                </View>
              ))}
            </View>
            {fact.placeholder && <Text style={sc.dev}>{copy.placeholderFact}</Text>}
            {fact.url && <TextLink label={copy.openSource} onPress={() => Linking.openURL(fact.url as string)} />}
          </>
        ) : (
          <>
            <Text style={sc.sub}>{copy.methodTitle}</Text>
            <People label={copy.heardFrom} />
            {copy.methodBody.map((line, i) => (
              <Text key={i} style={[sc.h2, { fontSize: 26, lineHeight: 31 }, i > 0 && { color: C.second }]}>
                {fill(line, { n: (base ?? 0).toLocaleString() })}
              </Text>
            ))}
          </>
        )}
      </ScrollView>
    </View>
  );
}

export function Consent({ copy, busy, onAgree }: { copy: Copy; busy: boolean; onAgree: () => void }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[sc.screen, { paddingTop: insets.top + 40, paddingBottom: insets.bottom + 32 }]}>
      <Text style={sc.sub}>{copy.consentTitle}</Text>
      <View style={{ gap: 28 }}>
        {copy.consentBody.map((line, i) => (
          <Text key={i} style={[sc.h2, i > 0 && { color: C.second }]}>
            {line}
          </Text>
        ))}
        <Pressable accessibilityRole="button" onPress={onAgree} disabled={busy} style={[sc.button, busy && { opacity: 0.5 }]}>
          <Text style={sc.buttonText}>{copy.agree}</Text>
        </Pressable>
      </View>
    </View>
  );
}

// What the World says when the app opens. One opening at most, picked by the backend.
export function Home({
  copy,
  open,
  onTalk,
  onType,
  onMap,
  onYou,
}: {
  copy: Copy;
  open: Open;
  onTalk: () => void;
  onType: () => void;
  onMap: () => void;
  onYou: () => void;
}) {
  const insets = useSafeAreaInsets();
  const o = open.opening;

  let body: React.ReactNode;
  if (!open.unlocked || !o) {
    const people = open.people.toLocaleString(open.language === 'it' ? 'it-IT' : 'en-US');
    body = (
      <View style={{ gap: 18, justifyContent: 'center', flex: 1 }}>
        {!open.unlocked && (
          <Rise delay={200}>
            <Text style={sc.hero}>{copy.hi}</Text>
          </Rise>
        )}
        {!open.unlocked && (
          <Rise delay={1300}>
            <Text style={sc.hero}>{fill(copy.weAre, { n: people })}</Text>
          </Rise>
        )}
        <Rise delay={open.unlocked ? 200 : 2400}>
          <Text style={sc.hero}>{copy.onMind}</Text>
        </Rise>
      </View>
    );
  } else if (o.kind === 'daily') {
    body = (
      <View style={{ gap: 16, justifyContent: 'center', flex: 1 }}>
        <Text style={sc.label}>{o.label}</Text>
        <Text style={sc.daily}>{o.lines[0]}</Text>
      </View>
    );
  } else if (o.kind === 'close') {
    body = (
      <View style={{ gap: 36 }}>
        <Lobes size={176} color={C.agreed} overlap={132} drift />
        <Text style={sc.h2}>{o.lines.join(' ')}</Text>
      </View>
    );
  } else if (o.kind === 'needs') {
    body = (
      <View style={{ gap: 24 }}>
        <Text style={sc.h2}>{o.lines.join(' ')}</Text>
        {o.quote && (
          <View style={sc.quote}>
            <Text style={sc.quoteLabel}>{o.quote_label}</Text>
            <Text style={sc.quoteText}>{o.quote}</Text>
          </View>
        )}
      </View>
    );
  } else {
    body = (
      <View style={{ gap: 20 }}>
        <Text style={sc.h2}>{o.lines.join(' ')}</Text>
        <People label={copy.heardFrom} />
      </View>
    );
  }

  return (
    <View style={[sc.full, { paddingTop: insets.top, paddingBottom: insets.bottom + 8 }]}>
      <ScrollView contentContainerStyle={[sc.main, { paddingTop: 24 }]}>
        {open.sample && <SampleTag label={copy.sample} />}
        <View style={{ flex: 1 }} />
        {body}
      </ScrollView>
      {open.unlocked ? (
        <Nav copy={copy} big unlocked onMap={onMap} onTalk={onTalk} onYou={onYou} />
      ) : (
        <View style={{ alignItems: 'center' }}>
          <Mic big label={copy.talkToWorld} onPress={onTalk} />
        </View>
      )}
      <TextLink label={copy.typeInstead} onPress={onType} />
    </View>
  );
}

export const sc = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.ground, paddingHorizontal: 28, justifyContent: 'space-between' },
  full: { flex: 1, backgroundColor: C.ground },
  main: { flexGrow: 1, paddingHorizontal: 28, paddingBottom: 44, gap: 20 },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logoDot: { width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(245, 245, 243, 0.55)' },
  brandText: { fontFamily: F.semi, fontSize: 22, color: C.text },
  hero: { fontFamily: F.regular, fontSize: 46, lineHeight: 49, letterSpacing: -0.9, color: C.text },
  h1: { fontFamily: F.regular, fontSize: 42, lineHeight: 45, letterSpacing: -0.8, color: C.text },
  h2: { fontFamily: F.regular, fontSize: 32, lineHeight: 36, letterSpacing: -0.6, color: C.text },
  sub: { fontFamily: F.regular, fontSize: 18, lineHeight: 24, color: C.second },
  label: { fontFamily: F.regular, fontSize: 16, color: C.second },
  daily: { fontFamily: F.regular, fontSize: 56, lineHeight: 57, letterSpacing: -1.4, color: C.text },
  dev: { fontFamily: F.mono, fontSize: 12, lineHeight: 17, color: C.third, textAlign: 'center' },
  button: { height: 60, borderRadius: 30, backgroundColor: C.paper, alignItems: 'center', justifyContent: 'center' },
  buttonText: { fontFamily: F.semi, fontSize: 18, color: C.ground },
  quote: { gap: 10, paddingVertical: 22, paddingHorizontal: 24, borderRadius: 24, backgroundColor: C.paper },
  quoteLabel: { fontFamily: F.regular, fontSize: 14, color: '#4F4F4C' },
  quoteText: { fontFamily: F.medium, fontSize: 25, lineHeight: 29, letterSpacing: -0.25, color: C.ink },
  block: { gap: 14, padding: 18, borderWidth: 1, borderColor: C.border },
  blockRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 16 },
  rule: { height: 1, backgroundColor: C.line },
  mono: { fontFamily: F.mono, fontSize: 14, lineHeight: 19, color: C.second },
});

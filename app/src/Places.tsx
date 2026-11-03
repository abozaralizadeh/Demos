import { useRef, useState } from 'react';
import { Alert, Pressable, ScrollView, Share, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Line } from 'react-native-svg';
import { publicUrl, type Area, type Card, type Lang, type MapData, type MapTopic, type YouData } from './api';
import { VALUE_WORDS, fill, type Copy } from './copy';
import { C, F, gapColor, rgba } from './theme';
import { Nav, SampleTag } from './ui';

type Tabs = { onMap: () => void; onTalk: () => void; onYou: () => void };

// The design's map is drawn on a 390 by 548 field. Topics keep those positions.
const FIELD = { w: 390, h: 548 };

function bubble(t: MapTopic) {
  const r = t.radius;
  const shy = t.thin || t.paused || t.gap === null;
  const g = shy ? 0 : (t.gap as number);
  const lobe = Math.round(r * (0.62 + 0.38 * (1 - g)));
  const apart = g * 2 * lobe * 0.9;
  const angle = (t.tilt * Math.PI) / 180;
  const dx = (Math.cos(angle) * apart) / 2;
  const dy = (Math.sin(angle) * apart) / 2;
  const w = Math.round(2 * lobe + 2 * Math.abs(dx));
  const h = Math.round(2 * lobe + 2 * Math.abs(dy));
  return { lobe, dx, dy, w, h, shy, color: shy ? C.mixed : gapColor(g) };
}

const AREAS: Area[] = ['milan', 'italy', 'world'];

// iOS switches are green by default. Here colour only ever measures something, so they're black and white.
const mono = (on: boolean) => ({
  trackColor: { false: C.track, true: C.text },
  thumbColor: on ? C.ink : C.text,
  ios_backgroundColor: C.track,
});

export function MapScreen({
  copy,
  data,
  sample,
  area,
  preview,
  onArea,
  onTopic,
  ...tabs
}: Tabs & {
  copy: Copy;
  data: MapData | null;
  sample: boolean;
  area: Area;
  preview: boolean;
  onArea: (a: Area) => void;
  onTopic: (t: MapTopic) => void;
}) {
  const insets = useSafeAreaInsets();
  const [size, setSize] = useState({ w: 0, h: 0 });
  const k = size.w ? Math.min(size.w / FIELD.w, size.h / FIELD.h) : 0;
  const left = (size.w - FIELD.w * k) / 2;
  const byId = Object.fromEntries((data?.topics ?? []).map((t) => [t.id, t]));

  return (
    <View style={[pl.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 8 }]}>
      <View style={pl.header}>
        <View style={{ flexDirection: 'row', gap: 6 }}>
          {(preview ? AREAS : (['milan'] as Area[])).map((a) => (
            <Pressable
              key={a}
              accessibilityRole="button"
              accessibilityState={{ selected: a === area }}
              onPress={() => onArea(a)}
              style={a === area ? pl.chipOn : pl.chip}
            >
              <Text style={a === area ? pl.chipOnText : pl.chipText}>{copy.areas[a]}</Text>
            </Pressable>
          ))}
        </View>
        {sample && <SampleTag label={copy.sample} />}
      </View>
      <View style={{ flex: 1 }} onLayout={(e) => setSize({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}>
        {k > 0 && data && (
          <>
            <Svg width={size.w} height={size.h} style={StyleSheet.absoluteFill}>
              {data.links.map((l, i) => {
                const a = byId[l.topic_a];
                const b = byId[l.topic_b];
                return (
                  <Line
                    key={i}
                    x1={left + a.x * k}
                    y1={a.y * k}
                    x2={left + b.x * k}
                    y2={b.y * k}
                    stroke={C.track}
                    strokeWidth={1}
                  />
                );
              })}
            </Svg>
            {data.topics.map((t) => {
              const b = bubble(t);
              const d = b.lobe * 2 * k;
              const state = t.paused ? copy.paused : b.shy ? copy.tooFew : '';
              return (
                <Pressable
                  key={t.id}
                  accessibilityRole="button"
                  accessibilityLabel={`${t.label}${state ? ', ' + state : ''}`}
                  onPress={() => onTopic(t)}
                  style={{
                    position: 'absolute',
                    left: left + (t.x - b.w / 2) * k,
                    top: (t.y - b.h / 2) * k,
                    width: b.w * k,
                    height: b.h * k,
                  }}
                >
                  <View
                    style={{
                      position: 'absolute',
                      left: (b.w / 2 - b.dx - b.lobe) * k,
                      top: (b.h / 2 - b.dy - b.lobe) * k,
                      width: d,
                      height: d,
                      borderRadius: d / 2,
                      backgroundColor: b.shy ? 'transparent' : rgba(b.color, 0.32),
                      borderWidth: b.shy ? 1.5 : 0,
                      borderStyle: 'dashed',
                      borderColor: C.third,
                    }}
                  />
                  {!b.shy && (
                    <View
                      style={{
                        position: 'absolute',
                        left: (b.w / 2 + b.dx - b.lobe) * k,
                        top: (b.h / 2 + b.dy - b.lobe) * k,
                        width: d,
                        height: d,
                        borderRadius: d / 2,
                        backgroundColor: rgba(b.color, 0.32),
                      }}
                    />
                  )}
                  <View style={{ position: 'absolute', top: 0, bottom: 0, left: -32, right: -32, alignItems: 'center', justifyContent: 'center' }}>
                    <Text
                      style={{
                        fontFamily: F.semi,
                        color: '#FFFFFF',
                        textAlign: 'center',
                        fontSize: (t.radius >= 60 ? 16 : t.radius >= 40 ? 14 : 12) * Math.min(1, k + 0.1),
                        lineHeight: (t.radius >= 60 ? 17 : t.radius >= 40 ? 15 : 13) * Math.min(1, k + 0.1),
                      }}
                    >
                      {t.label}
                    </Text>
                  </View>
                </Pressable>
              );
            })}
          </>
        )}
      </View>
      <View style={pl.legend}>
        <View style={pl.legendSide}>
          <Text style={pl.legendText}>{copy.divided}</Text>
          <View style={[pl.sw, { backgroundColor: rgba(C.divided, 0.7) }]} />
          <View style={[pl.sw, { backgroundColor: rgba(C.divided, 0.7), marginLeft: -3 }]} />
          <View style={[pl.sw, { backgroundColor: rgba(C.mixed, 0.8) }]} />
          <View style={[pl.sw, { backgroundColor: rgba(C.mixed, 0.8), marginLeft: -9 }]} />
          <View style={[pl.sw, { width: 13, height: 13, backgroundColor: rgba(C.agreed, 0.7) }]} />
          <Text style={pl.legendText}>{copy.agreement}</Text>
        </View>
        <View style={pl.legendSide}>
          <View style={[pl.sw, { width: 13, height: 13, backgroundColor: 'transparent', borderWidth: 1.5, borderStyle: 'dashed', borderColor: C.third }]} />
          <Text style={pl.legendText}>{copy.tooFew}</Text>
        </View>
      </View>
      <Nav copy={copy} unlocked current="map" {...tabs} />
    </View>
  );
}

function Mark({ value }: { value: string }) {
  return (
    <View style={pl.mark}>
      {value === 'agree' && <View style={[StyleSheet.absoluteFill, { backgroundColor: C.text }]} />}
      {value === 'partly' && <View style={pl.half} />}
      {value === 'disagree' && <View style={pl.minus} />}
    </View>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <View style={{ flex: 1, gap: 4 }}>
      <Text style={pl.big}>{value.toLocaleString()}</Text>
      <Text style={pl.small}>{label}</Text>
    </View>
  );
}

export function YouScreen({
  copy,
  lang,
  data,
  sample,
  onAgreement,
  onLanguage,
  onExport,
  onDelete,
  notifications,
  onNotifications,
  preview,
  anonymous,
  name,
  onAnonymous,
  onWithdraw,
  ...tabs
}: Tabs & {
  copy: Copy;
  lang: Lang;
  data: YouData | null;
  sample: boolean;
  onAgreement: (id: number) => void;
  onLanguage: () => void;
  onExport: () => void;
  onDelete: () => void;
  notifications: boolean;
  onNotifications: (on: boolean) => void;
  preview: boolean;
  anonymous: boolean;
  name: string | null;
  onAnonymous: (anonymous: boolean, name?: string) => void;
  onWithdraw: () => void;
}) {
  const [naming, setNaming] = useState(false);
  const typed = useRef(name ?? '');
  const insets = useSafeAreaInsets();
  const words = VALUE_WORDS[lang];
  const travel = data?.travel;
  const share = travel && travel.heard ? Math.round((travel.changed / travel.heard) * 100) : 0;

  return (
    <View style={[pl.screen, { paddingTop: insets.top, paddingBottom: insets.bottom + 8 }]}>
      <ScrollView contentContainerStyle={[pl.you, { paddingTop: 32 }]} keyboardShouldPersistTaps="handled">
        {sample && <SampleTag label={copy.sample} />}
        <Text style={pl.title}>{copy.youTitle}</Text>

        <View style={pl.section}>
          <Text style={pl.h2}>{copy.travel}</Text>
          {travel?.words ? <Text style={pl.quote}>{travel.words}</Text> : null}
          {travel && travel.heard > 0 ? (
            <>
              <View style={{ flexDirection: 'row', gap: 16 }}>
                <Stat value={travel.heard} label={copy.heardIt} />
                <Stat value={travel.changed} label={copy.changed} />
              </View>
              <View style={pl.crowd} accessibilityLabel={`${share} in 100`}>
                {Array.from({ length: 100 }, (_, i) => (
                  <View key={i} style={[pl.person, { backgroundColor: i < share ? C.text : C.track }]} />
                ))}
              </View>
            </>
          ) : (
            <Text style={pl.muted}>{copy.nobodyYet}</Text>
          )}
        </View>

        <View style={[pl.section, { gap: 6 }]}>
          <Text style={pl.h2}>{copy.believe}</Text>
          {(data?.views ?? []).map((v) => (
            <View key={v.stance_id} style={pl.row}>
              <Mark value={v.value} />
              <Text style={pl.rowText}>{v.claim}</Text>
              <Text style={pl.small}>{words[v.value]}</Text>
            </View>
          ))}
          {data && !data.views.length && <Text style={pl.muted}>{copy.nothingYet}</Text>}
        </View>

        {data?.moved && (
          <View style={pl.section}>
            <Text style={pl.h2}>{copy.openMind}</Text>
            <Text style={pl.was}>
              {data.moved.claim}: {words[data.moved.old_value]}
            </Text>
            <Text style={pl.arrow}>↓</Text>
            <Text style={pl.now}>
              {data.moved.claim}: {words[data.moved.now_value]}
            </Text>
            {data.moved.because && <Text style={pl.small}>{fill(copy.movedAfter, { because: data.moved.because })}</Text>}
          </View>
        )}

        <View style={pl.section}>
          <Text style={pl.h2}>{copy.bridges}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
            <Text style={pl.big}>{data?.bridges ?? 0}</Text>
            <Text style={pl.rowText}>{copy.bridgesN}</Text>
          </View>
        </View>

        <View style={pl.section}>
          <Text style={pl.h2}>{copy.agreements}</Text>
          {(data?.agreements ?? []).map((a) => (
            <Pressable key={a.id} accessibilityRole="button" onPress={() => onAgreement(a.id)} style={pl.card}>
              <Text style={pl.cardText}>{a.text}</Text>
              <View style={pl.cardFoot}>
                <Text style={pl.small}>{a.sent ? copy.sent : a.state === 'live' ? copy.live : copy.lapsed}</Text>
                {a.meters.length > 0 && (
                  <Text style={pl.mono}>
                    {a.meters[a.meters.length - 1].pct}% {copy.overall}
                  </Text>
                )}
              </View>
            </Pressable>
          ))}
          {data && !data.agreements.length && <Text style={pl.muted}>{copy.nothingYet}</Text>}
        </View>

        <View style={[pl.section, { gap: 0 }]}>
          <View style={pl.settingRow}>
            <Text style={pl.rowText}>{copy.notifications}</Text>
            <Switch
              value={notifications}
              onValueChange={onNotifications}
              accessibilityLabel={copy.notifications}
              {...mono(notifications)}
            />
          </View>
          {preview && (
            <View style={pl.settingRow}>
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={pl.rowText}>{copy.anonymous}</Text>
                <Text style={pl.preview}>{copy.preview}</Text>
              </View>
              <Switch
                value={anonymous && !naming}
                onValueChange={(on) => (on ? (setNaming(false), onAnonymous(true)) : setNaming(true))}
                accessibilityLabel={copy.anonymous}
                {...mono(anonymous && !naming)}
              />
            </View>
          )}
          {preview && (naming || !anonymous) && (
            <View style={{ gap: 10, paddingBottom: 16 }}>
              <Text style={pl.h2}>{copy.nameTitle}</Text>
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <TextInput
                  defaultValue={name ?? ''}
                  onChangeText={(t) => (typed.current = t)}
                  placeholder={copy.namePlaceholder}
                  placeholderTextColor={C.third}
                  autoCapitalize="words"
                  style={pl.input}
                />
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    setNaming(false);
                    onAnonymous(false, typed.current);
                  }}
                  style={pl.save}
                >
                  <Text style={pl.saveText}>{copy.save}</Text>
                </Pressable>
              </View>
              <Text style={pl.small}>{copy.nameHint}</Text>
            </View>
          )}
          {[
            { label: copy.language, onPress: onLanguage },
            { label: copy.exportMe, onPress: onExport },
            {
              label: copy.withdraw,
              onPress: () =>
                Alert.alert(copy.withdrawQ, copy.withdrawBody, [
                  { text: copy.cancel, style: 'cancel' },
                  { text: copy.withdraw, style: 'destructive', onPress: onWithdraw },
                ]),
            },
            {
              label: copy.deleteAll,
              onPress: () =>
                Alert.alert(copy.deleteQ, copy.deleteBody, [
                  { text: copy.cancel, style: 'cancel' },
                  { text: copy.deleteAll, style: 'destructive', onPress: onDelete },
                ]),
            },
          ].map((b) => (
            <Pressable key={b.label} accessibilityRole="button" onPress={b.onPress} style={pl.setting}>
              <Text style={pl.rowText}>{b.label}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
      <Nav copy={copy} unlocked current="you" {...tabs} />
    </View>
  );
}

export function AgreementScreen({
  copy,
  lang,
  card,
  sample,
  onAsk,
  onSign,
  ...tabs
}: Tabs & { copy: Copy; lang: Lang; card: Card | null; sample: boolean; onAsk: () => void; onSign: () => void }) {
  const insets = useSafeAreaInsets();
  if (!card) return <View style={pl.screen} />;
  const status = card.state === 'live' ? copy.live : card.state === 'lapsed' ? copy.lapsed : copy.candidate;
  const askLabel = card.sent
    ? copy.sent
    : card.asked
      ? fill(copy.asked, { n: card.requests, need: card.requests_needed })
      : copy.askSend;

  return (
    <View style={[pl.screen, { paddingTop: insets.top, paddingBottom: insets.bottom + 8 }]}>
      <ScrollView contentContainerStyle={[pl.you, { paddingTop: 28, gap: 28, flexGrow: 1 }]}>
        <View style={pl.agreeHead}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={{ flexDirection: 'row' }}>
              <View style={pl.green} />
              <View style={[pl.green, { marginLeft: -13 }]} />
            </View>
            <Text style={[pl.rowText, { flex: 0 }]}>{copy.agreement}</Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            {sample && <SampleTag label={copy.sample} />}
            <Text style={pl.small}>{status}</Text>
          </View>
        </View>
        <View style={{ flex: 1 }} />
        <Text style={pl.agreeText}>{card.text}</Text>
        <View style={{ gap: 14 }}>
          {card.meters.map((m) => (
            <View key={m.label} style={pl.meter} accessibilityLabel={`${m.label} ${m.pct}%`}>
              <Text style={[pl.rowText, { width: 74, flex: 0 }]}>{m.label}</Text>
              <View style={pl.meterTrack}>
                <View style={{ width: `${m.pct}%`, borderRadius: 4, backgroundColor: C.agreed }} />
              </View>
              <Text style={[pl.mono, { width: 44, textAlign: 'right' }]}>{m.pct}%</Text>
            </View>
          ))}
          {card.paused && <Text style={pl.small}>{copy.paused}</Text>}
        </View>
        <View style={{ gap: 10 }}>
          <Pressable
            accessibilityRole="button"
            onPress={onAsk}
            disabled={card.asked || card.sent || card.state !== 'live'}
            style={[pl.primary, (card.asked || card.sent || card.state !== 'live') && { opacity: 0.6 }]}
          >
            <Text style={pl.primaryText}>{askLabel}</Text>
          </Pressable>
          {card.petition && card.state === 'live' && (
            <Pressable accessibilityRole="button" onPress={onSign} style={[pl.secondary, card.petition.signed && pl.signed]}>
              <Text style={[pl.rowText, { flex: 0 }]}>
                {card.petition.signed ? fill(copy.signedPetition, { n: card.petition.signatures }) : copy.usePetition}
              </Text>
            </Pressable>
          )}
          <Pressable
            accessibilityRole="button"
            onPress={() => Share.share({ message: `${card.text}\n${publicUrl(card.id, lang)}` })}
            style={pl.secondary}
          >
            <Text style={[pl.rowText, { flex: 0 }]}>{copy.share}</Text>
          </Pressable>
        </View>
      </ScrollView>
      <Nav copy={copy} unlocked {...tabs} />
    </View>
  );
}

const pl = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.ground },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 28, paddingBottom: 12 },
  chipOn: { height: 44, paddingHorizontal: 18, borderRadius: 22, backgroundColor: C.paper, justifyContent: 'center' },
  chipOnText: { fontFamily: F.medium, fontSize: 16, color: C.ground },
  chip: { height: 44, paddingHorizontal: 16, borderRadius: 22, borderWidth: 1, borderColor: C.border, justifyContent: 'center' },
  chipText: { fontFamily: F.medium, fontSize: 16, color: C.second },
  settingRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, borderTopWidth: 1, borderTopColor: C.line, paddingVertical: 8 },
  preview: { fontFamily: F.mono, fontSize: 11, color: C.third },
  input: { flex: 1, height: 52, paddingHorizontal: 18, borderRadius: 26, borderWidth: 1, borderColor: C.border, backgroundColor: C.field, color: C.text, fontFamily: F.regular, fontSize: 17 },
  save: { height: 52, paddingHorizontal: 20, borderRadius: 26, backgroundColor: C.paper, justifyContent: 'center' },
  saveText: { fontFamily: F.semi, fontSize: 16, color: C.ground },
  signed: { borderColor: C.agreed },
  legend: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 28, paddingVertical: 12 },
  legendSide: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendText: { fontFamily: F.regular, fontSize: 12.5, color: C.second, marginHorizontal: 3 },
  sw: { width: 11, height: 11, borderRadius: 7 },
  you: { paddingHorizontal: 28, paddingBottom: 32, gap: 44 },
  title: { fontFamily: F.regular, fontSize: 46, lineHeight: 48, letterSpacing: -1.1, color: C.text },
  section: { gap: 14 },
  h2: { fontFamily: F.regular, fontSize: 15, color: C.second },
  quote: { fontFamily: F.regular, fontSize: 26, lineHeight: 30, letterSpacing: -0.4, color: C.text },
  big: { fontFamily: F.mono, fontSize: 38, letterSpacing: -1.5, color: C.text },
  small: { fontFamily: F.regular, fontSize: 14, lineHeight: 19, color: C.second },
  muted: { fontFamily: F.regular, fontSize: 18, lineHeight: 23, color: C.third },
  mono: { fontFamily: F.mono, fontSize: 15, color: C.text },
  crowd: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  person: { width: 11, height: 11, borderRadius: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, borderTopWidth: 1, borderTopColor: C.line },
  rowText: { flex: 1, fontFamily: F.regular, fontSize: 18, lineHeight: 22, color: C.text },
  mark: { width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: C.text, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  half: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 7, backgroundColor: C.text },
  minus: { width: 10, height: 2, backgroundColor: C.text },
  was: { fontFamily: F.regular, fontSize: 18, lineHeight: 23, color: C.third },
  arrow: { fontFamily: F.regular, fontSize: 20, color: C.second },
  now: { fontFamily: F.regular, fontSize: 22, lineHeight: 26, color: C.text },
  card: { gap: 12, paddingVertical: 18, paddingHorizontal: 20, borderRadius: 22, borderWidth: 1, borderColor: C.border },
  cardText: { fontFamily: F.regular, fontSize: 18, lineHeight: 22, color: C.text },
  cardFoot: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  setting: { minHeight: 52, justifyContent: 'center', borderTopWidth: 1, borderTopColor: C.line },
  agreeHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  green: { width: 18, height: 18, borderRadius: 9, backgroundColor: rgba(C.agreed, 0.7) },
  agreeText: { fontFamily: F.regular, fontSize: 34, lineHeight: 38, letterSpacing: -0.7, color: C.text },
  meter: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  meterTrack: { flex: 1, height: 8, borderRadius: 4, backgroundColor: C.line, flexDirection: 'row' },
  primary: { height: 58, borderRadius: 29, backgroundColor: C.paper, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  primaryText: { fontFamily: F.semi, fontSize: 17, color: C.ground, textAlign: 'center' },
  secondary: { height: 52, borderRadius: 26, borderWidth: 1, borderColor: C.border, alignItems: 'center', justifyContent: 'center' },
});

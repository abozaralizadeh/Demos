import * as Speech from 'expo-speech';
import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from 'expo-speech-recognition';
import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Linking,
  Pressable,
  ScrollView,
  type ScrollViewInstance,
  StyleSheet,
  Text,
  TextInput,
  type TextInputInstance,
  View,
} from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { Lang, MirrorRow, Reply, Value } from './api';
import type { Copy } from './copy';
import { Problem } from './Screens';
import { C, F } from './theme';
import { Data, Dome, Heard, Lobes, Mic, Nav, People, SampleTag, TextLink, ink, type Tone } from './ui';

const CYCLE: Value[] = ['agree', 'partly', 'unsure', 'disagree'];

type Props = {
  copy: Copy;
  lang: Lang;
  sample: boolean;
  reply: Reply;
  heard: string;
  unlocked: boolean;
  busy: boolean;
  error: string | null;
  startWith: 'voice' | 'type' | null;
  onSay: (text: string) => void;
  onFix: (row: MirrorRow, value: Value) => Promise<string | null>;
  onReport: (turnId: number) => void;
  onSource: (factId: number | null, base: number | null) => void;
  onRetry: () => void;
  onMap: () => void;
  onYou: () => void;
};

export function Talk(props: Props) {
  const { copy, lang, reply, busy } = props;
  const insets = useSafeAreaInsets();
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [typing, setTyping] = useState(props.startWith === 'type');
  const draft = useRef('');
  const field = useRef<TextInputInstance>(null);
  const scroll = useRef<ScrollViewInstance>(null);
  const [trouble, setTrouble] = useState<'denied' | 'failed' | null>(null);
  const spoke = useRef(false);
  const heardRef = useRef('');
  const listeningRef = useRef(false);

  useSpeechRecognitionEvent('result', (e) => {
    heardRef.current = e.results[0]?.transcript ?? '';
    setTranscript(heardRef.current);
  });
  useSpeechRecognitionEvent('end', () => {
    if (!listeningRef.current) return;
    listeningRef.current = false;
    setListening(false);
    const text = heardRef.current.trim();
    if (text) {
      spoke.current = true;
      props.onSay(text);
    }
  });
  useSpeechRecognitionEvent('error', (e) => {
    listeningRef.current = false;
    setListening(false);
    if (e.error === 'aborted') return;
    setTrouble(e.error === 'not-allowed' || e.error === 'service-not-allowed' ? 'denied' : 'failed');
  });

  async function listen() {
    Speech.stop();
    try {
      const allowed = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!allowed.granted) {
        setTrouble('denied');
        return;
      }
      setTrouble(null);
      heardRef.current = '';
      setTranscript('');
      listeningRef.current = true;
      setListening(true);
      setTyping(false);
      // On-device only, so the audio never leaves the phone.
      ExpoSpeechRecognitionModule.start({
        lang: lang === 'it' ? 'it-IT' : 'en-US',
        interimResults: true,
        continuous: true,
        requiresOnDeviceRecognition: true,
        addsPunctuation: true,
      });
    } catch {
      setTrouble('failed');
    }
  }

  function typeInstead() {
    setTrouble(null);
    setTyping(true);
  }

  useEffect(() => {
    if (props.startWith === 'voice') listen();
    // Only when the talk opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Read the World's answer aloud only to people who spoke to it.
  useEffect(() => {
    if (spoke.current && reply.lines.length && !listening) {
      Speech.speak(reply.lines.join(' '), { language: lang === 'it' ? 'it-IT' : 'en-US' });
    }
    return () => {
      Speech.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reply.turn_id]);

  // The field's own text wins over state, which can lag behind fast typing.
  function send(fromField?: string) {
    const text = (fromField ?? draft.current).trim();
    if (!text || busy) return;
    spoke.current = false;
    draft.current = '';
    field.current?.clear();
    props.onSay(text);
  }

  const tone: Tone = listening ? 'dark' : reply.theme === 'white' ? 'white' : 'dark';
  const t = ink(tone);

  if (trouble === 'denied') {
    return (
      <Problem
        title={copy.micDeniedTitle}
        body={copy.micDeniedBody}
        action={copy.openSettings}
        onAction={() => Linking.openSettings()}
        other={copy.typeInstead}
        onOther={typeInstead}
      />
    );
  }
  if (trouble === 'failed') {
    return (
      <Problem
        title={copy.speechFailedTitle}
        body={copy.speechFailedBody}
        action={copy.retry}
        onAction={listen}
        other={copy.typeInstead}
        onOther={typeInstead}
      />
    );
  }

  if (listening) {
    return (
      <View style={[st.screen, { backgroundColor: C.ground, paddingTop: insets.top }]}>
        <Dome active />
        <View style={st.listenTop}>
          <Text style={st.prompt}>{reply.lines[reply.lines.length - 1] ?? copy.onMind}</Text>
          <Text style={st.live}>
            {transcript}
            <Text style={st.cursor}>|</Text>
          </Text>
        </View>
        <View style={[st.done, { paddingBottom: insets.bottom + 20 }]}>
          <Mic big filled label={copy.tapDone} onPress={() => ExpoSpeechRecognitionModule.stop()} />
          <Text style={st.doneText}>{copy.tapDone}</Text>
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView behavior="padding" style={[st.screen, { backgroundColor: t.bg }]}>
      {/* Pinned, so long replies scroll under it instead of under the clock. */}
      <View style={[st.tags, { paddingTop: insets.top + 24, paddingBottom: 12, paddingHorizontal: 28 }]}>
        <Text style={[st.ai, { color: t.second }]}>{copy.aiLabel}</Text>
        {props.sample && <SampleTag label={copy.sample} tone={tone} />}
      </View>
      <ScrollView
        ref={scroll}
        onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: true })}
        contentContainerStyle={st.main}
        keyboardShouldPersistTaps="handled"
      >
        <View style={{ flex: 1 }} />
        {props.error ? (
          <View style={{ gap: 16 }}>
            <Text style={[st.caption, { color: t.text }]}>{props.error}</Text>
            <TextLink label={copy.retry} tone={tone} onPress={props.onRetry} />
          </View>
        ) : (
          <Pressable
            onLongPress={() =>
              reply.turn_id &&
              Alert.alert(copy.reportQ, undefined, [
                { text: copy.cancel, style: 'cancel' },
                { text: copy.report, style: 'destructive', onPress: () => props.onReport(reply.turn_id!) },
              ])
            }
          >
            <Said reply={reply} heard={props.heard} copy={copy} tone={tone} onFix={props.onFix} onSource={props.onSource} />
          </Pressable>
        )}
        {busy && <ActivityIndicator color={t.second} style={{ alignSelf: 'flex-start' }} />}
      </ScrollView>
      <View style={st.pinned}>
        {typing && (
          <View style={st.typeRow}>
            <TextInput
              autoFocus
              ref={field}
              onChangeText={(text) => (draft.current = text)}
              onSubmitEditing={(e) => send(e.nativeEvent.text)}
              returnKeyType="send"
              placeholder={copy.placeholder}
              placeholderTextColor={C.third}
              accessibilityLabel={copy.sayHere}
              style={[st.input, tone === 'white' && st.inputWhite]}
            />
            <Pressable accessibilityRole="button" accessibilityLabel="Send" onPress={() => send()} style={[st.send, { backgroundColor: t.text }]}>
              <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
                <Path d="M12 19V5" stroke={t.bg} strokeWidth={2} strokeLinecap="round" />
                <Path d="M6 11l6-6 6 6" stroke={t.bg} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
              </Svg>
            </Pressable>
          </View>
        )}
      </View>
      <View style={{ paddingBottom: insets.bottom + 8 }}>
        <Nav
          copy={copy}
          tone={tone}
          big={!typing}
          outline={typing}
          unlocked={props.unlocked}
          onMap={props.onMap}
          onTalk={listen}
          onYou={props.onYou}
        />
        <TextLink label={typing ? copy.talkInstead : copy.typeInstead} tone={tone} onPress={() => (typing ? listen() : setTyping(true))} />
      </View>
    </KeyboardAvoidingView>
  );
}

// What the World said, laid out the way the design shows each move.
function Said({
  reply,
  heard,
  copy,
  tone,
  onFix,
  onSource,
}: {
  reply: Reply;
  heard: string;
  copy: Copy;
  tone: Tone;
  onFix: Props['onFix'];
  onSource: Props['onSource'];
}) {
  const t = ink(tone);
  const lines = reply.lines;
  const factId = reply.data?.fact_id;
  const factSource = factId ? () => onSource(factId, null) : undefined;
  const big = (text: string, extra?: object) => (
    <Text style={[st.caption, { color: t.text }, extra]}>{text}</Text>
  );

  switch (reply.move) {
    case 'mirror':
      if (!reply.mirror) break;
      return (
        <View style={st.block}>
          <Heard text={reply.mirror.heard} tone={tone} />
          {big(lines.join(' '), { fontSize: 36, lineHeight: 40 })}
          <View>
            {reply.mirror.rows.map((row, i) => (
              <MirrorLine key={`${row.stance_id ?? 'g'}-${i}`} row={row} onFix={onFix} />
            ))}
          </View>
          <Text style={[st.note, { color: t.second }]}>{reply.mirror.hint}</Text>
        </View>
      );
    case 'where_you_stand':
      return (
        <View style={st.block}>
          <Heard text={heard} tone={tone} />
          {big(lines.join(' '))}
          <View style={{ gap: 10 }}>
            {typeof reply.data?.bar === 'number' && (
              <View style={st.bar} accessibilityLabel={`${reply.data.bar}%`}>
                <View style={[st.barFill, { flex: reply.data.bar }]} />
                <View style={[st.barRest, { flex: 100 - reply.data.bar }]} />
              </View>
            )}
            {reply.source && (
              <People label={reply.source} tone={tone} onPress={() => onSource(null, reply.data?.base ?? null)} />
            )}
          </View>
        </View>
      );
    case 'challenge':
      return (
        <View style={st.block}>
          <Text style={[st.intro, { color: t.second }]}>{lines[0]}</Text>
          {big(lines.slice(1).join(' '), { fontFamily: F.medium, fontSize: 33, lineHeight: 37 })}
          {reply.foot && <People label={reply.foot} tone={tone} />}
        </View>
      );
    case 'inform':
      return (
        <View style={st.block}>
          <Heard text={heard} tone={tone} />
          {big(lines[0])}
          {reply.data ? (
            <Data block={reply.data} copy={copy} onSource={factSource} />
          ) : (
            lines.slice(1).map((l, i) => <View key={i}>{big(l)}</View>)
          )}
        </View>
      );
    case 'thin': {
      const factText = reply.data ? lines.find((l) => reply.data?.title && l.startsWith(reply.data.title)) : undefined;
      const words = lines.filter((l) => l !== factText);
      const last = words.pop() ?? '';
      return (
        <View style={st.block}>
          {big(words.join(' '))}
          {reply.data && <Data block={reply.data} copy={copy} onSource={factSource} />}
          {big(last)}
        </View>
      );
    }
    case 'bridge':
      return (
        <View style={[st.block, { gap: 28 }]}>
          <Lobes size={170} color={C.agreed} overlap={64} />
          <View style={{ gap: 14 }}>
            <Text style={[st.intro, { color: t.second }]}>{lines[0]}</Text>
            {big(reply.bridge ?? lines[1] ?? '')}
            {big(lines[lines.length - 1])}
          </View>
        </View>
      );
    case 'safety':
      // The "we" voice and every other flow stop here. The card puts help one tap away.
      return (
        <View style={st.block}>
          {big(lines[0], { fontSize: 28, lineHeight: 33 })}
          <View style={st.help}>
            <Text style={st.helpLabel}>{copy.helpNow}</Text>
            <Pressable accessibilityRole="button" onPress={() => Linking.openURL('tel:112')} style={st.helpCall}>
              <Text style={st.helpCallText}>{copy.call112}</Text>
            </Pressable>
            <Pressable accessibilityRole="button" onPress={() => Linking.openURL('tel:0223272327')} style={st.helpLine}>
              <Text style={st.helpLineText}>{copy.callFriend}</Text>
            </Pressable>
          </View>
          {big(lines[lines.length - 1], { fontSize: 24, lineHeight: 29 })}
        </View>
      );
  }
  return (
    <View style={st.block}>
      <Heard text={reply.move === 'listen' || reply.move === 'close' ? heard : ''} tone={tone} />
      {big(lines.join(' '))}
    </View>
  );
}

function MirrorLine({ row, onFix }: { row: MirrorRow; onFix: Props['onFix'] }) {
  const [value, setValue] = useState<Value | null>(row.value);
  const [word, setWord] = useState(row.word);
  const tappable = row.stance_id !== null && value !== null;

  async function cycle() {
    if (!tappable || !value) return;
    const next = CYCLE[(CYCLE.indexOf(value) + 1) % CYCLE.length];
    setValue(next);
    const fixed = await onFix(row, next);
    if (fixed) setWord(fixed);
  }

  return (
    <Pressable
      accessibilityRole={tappable ? 'button' : undefined}
      accessibilityLabel={`${row.claim}: ${word}. Tap to change.`}
      onPress={cycle}
      style={st.row}
    >
      <Mark value={value} />
      <Text style={st.rowText}>{row.claim}</Text>
      <Text style={st.rowWord}>{word}</Text>
    </Pressable>
  );
}

// Full is agree, half is partly, empty is unsure, a bar through it is disagree.
function Mark({ value }: { value: Value | null }) {
  return (
    <View style={st.mark}>
      {value === 'agree' && <View style={[StyleSheet.absoluteFill, { backgroundColor: C.text }]} />}
      {value === 'partly' && <View style={[st.half, { backgroundColor: C.text }]} />}
      {value === 'disagree' && <View style={st.minus} />}
      {value === null && <View style={st.groupDot} />}
    </View>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1 },
  main: { flexGrow: 1, paddingHorizontal: 28, paddingBottom: 24, gap: 20 },
  block: { gap: 22 },
  pinned: { paddingHorizontal: 28, paddingBottom: 8, gap: 10 },
  tags: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  ai: { flex: 1, fontFamily: F.regular, fontSize: 13, lineHeight: 17 },
  caption: { fontFamily: F.regular, fontSize: 32, lineHeight: 36, letterSpacing: -0.6 },
  intro: { fontFamily: F.regular, fontSize: 20, lineHeight: 25 },
  note: { fontFamily: F.regular, fontSize: 14, lineHeight: 19 },
  bar: { flexDirection: 'row', height: 8, gap: 2 },
  barFill: { borderRadius: 4, backgroundColor: C.text },
  barRest: { borderRadius: 4, backgroundColor: C.track },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: 60,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: C.line,
  },
  rowText: { flex: 1, fontFamily: F.regular, fontSize: 18, lineHeight: 22, color: C.text },
  rowWord: { fontFamily: F.regular, fontSize: 14, color: C.second },
  mark: { width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: C.text, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  half: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 7 },
  minus: { width: 10, height: 2, backgroundColor: C.text },
  groupDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: C.text },
  help: { gap: 12, padding: 20, borderRadius: 24, backgroundColor: C.paper },
  helpLabel: { fontFamily: F.regular, fontSize: 14, color: '#4F4F4C' },
  helpCall: { height: 56, borderRadius: 28, backgroundColor: C.ink, alignItems: 'center', justifyContent: 'center' },
  helpCallText: { fontFamily: F.semi, fontSize: 18, color: C.paper },
  helpLine: { minHeight: 56, borderRadius: 28, borderWidth: 1, borderColor: C.ink, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  helpLineText: { fontFamily: F.medium, fontSize: 16, color: C.ink, textAlign: 'center' },
  typeRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  input: {
    flex: 1,
    height: 56,
    paddingHorizontal: 20,
    borderRadius: 28,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.field,
    color: C.text,
    fontFamily: F.regular,
    fontSize: 17,
  },
  inputWhite: { backgroundColor: '#FFFFFF', color: C.ink, borderColor: C.third },
  send: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  listenTop: { paddingHorizontal: 28, paddingTop: 48, gap: 18 },
  prompt: { fontFamily: F.regular, fontSize: 19, lineHeight: 24, color: C.second },
  live: { fontFamily: F.regular, fontSize: 34, lineHeight: 38, letterSpacing: -0.7, color: C.text },
  cursor: { color: C.text, fontFamily: F.regular },
  done: { marginTop: 'auto', alignItems: 'center', gap: 8 },
  doneText: { height: 44, lineHeight: 44, fontFamily: F.regular, fontSize: 13, color: C.second },
});

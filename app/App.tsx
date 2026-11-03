import { BricolageGrotesque_400Regular, BricolageGrotesque_500Medium, BricolageGrotesque_600SemiBold } from '@expo-google-fonts/bricolage-grotesque';
import { DMMono_400Regular } from '@expo-google-fonts/dm-mono';
import { useFonts } from 'expo-font';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Pressable, Share, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  ApiError,
  api,
  forget,
  loadToken,
  signInDev,
  type Area,
  type Card,
  type DevCheck,
  type Fact,
  type Lang,
  type MapData,
  type MapTopic,
  type MirrorRow,
  type Open,
  type Reply,
  type Value,
  type YouData,
} from './src/api';
import { COPY } from './src/copy';
import { askToNotify, notifyDaily, stopNotifying } from './src/notify';
import { AgreementScreen, MapScreen, YouScreen } from './src/Places';
import { Consent, Home, NotifyAsk, Problem, SourceScreen, Verify } from './src/Screens';
import { Talk } from './src/Talk';
import { C, F } from './src/theme';

function ErrorStrip({ text, retry, onPress }: { text: string; retry: string; onPress: () => void }) {
  const insets = useSafeAreaInsets();
  return (
    <View
      accessibilityRole="alert"
      style={{
        position: 'absolute',
        top: insets.top + 8,
        left: 16,
        right: 16,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
        paddingVertical: 12,
        paddingHorizontal: 16,
        borderRadius: 16,
        backgroundColor: C.paper,
      }}
    >
      <Text style={{ flex: 1, fontFamily: F.regular, fontSize: 15, lineHeight: 20, color: C.ink }}>{text}</Text>
      <Pressable accessibilityRole="button" onPress={onPress} hitSlop={12}>
        <Text style={{ fontFamily: F.semi, fontSize: 15, color: C.ink }}>{retry}</Text>
      </Pressable>
    </View>
  );
}

type Place = 'boot' | 'verify' | 'refused' | 'consent' | 'home' | 'talk' | 'map' | 'you' | 'agreement';
type Refusal = 'minor' | 'failed' | 'offline';
// Source detail sits on top of the screen that opened it, so a talk keeps its place underneath.
type Source = { fact: Fact | null; base: number | null };

const deviceLang = (): Lang =>
  Intl.DateTimeFormat().resolvedOptions().locale.toLowerCase().startsWith('it') ? 'it' : 'en';

export default function App() {
  const [fontsReady] = useFonts({
    BricolageGrotesque_400Regular,
    BricolageGrotesque_500Medium,
    BricolageGrotesque_600SemiBold,
    DMMono_400Regular,
  });
  const [place, setPlace] = useState<Place>('boot');
  const [lang, setLang] = useState<Lang>(deviceLang());
  const [open, setOpen] = useState<Open | null>(null);
  const [reply, setReply] = useState<Reply | null>(null);
  const [heard, setHeard] = useState('');
  const [startWith, setStartWith] = useState<'voice' | 'type' | null>(null);
  const [map, setMap] = useState<MapData | null>(null);
  const [area, setArea] = useState<Area>('milan');
  const [you, setYou] = useState<YouData | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [refusal, setRefusal] = useState<Refusal>('failed');
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const copy = COPY[lang];
  // Read through a ref so switching language doesn't rebuild run, refresh and the boot effect.
  const langNow = useRef(lang);
  langNow.current = lang;

  // Every call goes through here, so a lost session sends people back to sign in.
  const run = useCallback(async <T,>(work: () => Promise<T>, again?: () => void): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await work();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        await forget();
        setPlace('verify');
      } else {
        setError(COPY[langNow.current].offline);
        setRetry(() => again ?? null);
      }
    } finally {
      setBusy(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    const o = await run(api.open, () => refresh());
    if (!o) return;
    setOpen(o);
    setLang(o.language);
    setPlace(o.consented ? 'home' : 'consent');
  }, [run]);

  useEffect(() => {
    loadToken().then((token) => (token ? refresh() : setPlace('verify')));
  }, [refresh]);

  async function verify(as?: DevCheck) {
    setBusy(true);
    try {
      await signInDev(lang, as);
    } catch (e) {
      // 403 is the age check. Any other answer means the check itself didn't go through.
      setRefusal(e instanceof ApiError ? (e.status === 403 ? 'minor' : 'failed') : 'offline');
      setPlace('refused');
      return;
    } finally {
      setBusy(false);
    }
    refresh();
  }

  async function agree() {
    const ok = await run(api.consent);
    if (ok) refresh();
  }

  async function talk(mode: 'voice' | 'type', openedBy = 'person', topicId: string | null = null) {
    const first = await run(() => api.start(openedBy, topicId), () => talk(mode, openedBy, topicId));
    if (!first) return;
    setReply(first);
    setHeard('');
    setStartWith(mode);
    setPlace('talk');
  }

  function talkFromHome(mode: 'voice' | 'type') {
    const o = open?.unlocked ? open.opening : null;
    talk(mode, o?.kind ?? 'person', o?.topic_id ?? null);
  }

  async function say(text: string) {
    if (!reply) return;
    if (reply.ended) {
      // A closed talk can't take more words, so a new one starts with them.
      const fresh = await run(() => api.start());
      if (!fresh) return;
      return sayIn(fresh.conversation_id, text);
    }
    return sayIn(reply.conversation_id, text);
  }

  async function sayIn(conversationId: string, text: string) {
    setHeard(text);
    const next = await run(() => api.say(conversationId, text), () => sayIn(conversationId, text));
    if (!next) return;
    setReply(next);
    if (next.unlocked && open && !open.unlocked) setOpen({ ...open, unlocked: true });
  }

  async function fix(row: MirrorRow, value: Value) {
    if (!reply || row.stance_id === null) return null;
    const res = await run(() => api.fix(reply.conversation_id, row.stance_id as number, value));
    if (res && open && !open.unlocked) setOpen({ ...open, unlocked: true });
    return res?.word ?? null;
  }

  async function report(turnId: number) {
    const res = await run(() => api.report(turnId));
    if (res) Alert.alert(res.message);
  }

  async function openSource(factId: number | null, base: number | null) {
    if (factId === null) return setSource({ fact: null, base });
    const fact = await run(() => api.fact(factId));
    if (fact) setSource({ fact, base: null });
  }

  async function showMap(a: Area = area) {
    const m = await run(() => api.map(a), () => showMap(a));
    if (!m) return;
    setMap(m);
    setArea(a);
    setPlace('map');
  }

  async function showYou() {
    const y = await run(api.you, showYou);
    if (!y) return;
    setYou(y);
    setPlace('you');
  }

  async function showAgreement(id: number) {
    const c = await run(() => api.agreement(id));
    if (!c) return;
    setCard(c);
    setPlace('agreement');
  }

  function openTopic(t: MapTopic) {
    if (t.agreement_id) showAgreement(t.agreement_id);
    else talk('voice', 'map', t.id);
  }

  async function askToSend() {
    if (!card) return;
    const ok = await run(() => api.askToSend(card.id));
    if (ok) showAgreement(card.id);
  }

  async function sign() {
    if (!card) return;
    if (open?.anonymous) return Alert.alert(copy.petitionNeedsName, copy.petitionNeedsNameBody);
    const ok = await run(() => api.sign(card.id));
    if (ok) showAgreement(card.id);
  }

  async function switchLanguage() {
    const next: Lang = lang === 'it' ? 'en' : 'it';
    const ok = await run(() => api.settings({ language: next }));
    if (!ok) return;
    setLang(next);
    const y = await run(api.you);
    if (y) setYou(y);
  }

  async function setNotifications(on: boolean) {
    if (on) return setAsking(true);
    await stopNotifying();
    const ok = await run(() => api.settings({ notifications: false }));
    if (ok && open) setOpen({ ...open, notifications: false });
  }

  async function notifyYes() {
    setAsking(false);
    if (!(await askToNotify())) return Alert.alert(copy.notifyBlocked);
    await notifyDaily(copy);
    const ok = await run(() => api.settings({ notifications: true }));
    if (ok && open) setOpen({ ...open, notifications: true });
  }

  async function setAnonymous(anonymous: boolean, name?: string) {
    const clean = (name ?? '').trim();
    if (!anonymous && clean.length < 2) return Alert.alert(copy.nameTitle, copy.nameHint);
    const ok = await run(() => api.settings(anonymous ? { anonymous } : { anonymous, display_name: clean }));
    if (ok && open) setOpen({ ...open, anonymous, display_name: anonymous ? null : clean });
  }

  async function withdraw() {
    const ok = await run(api.withdraw);
    if (!ok) return;
    await stopNotifying();
    setReply(null);
    setYou(null);
    refresh();
  }

  async function exportData() {
    const data = await run(api.exportMe);
    if (data) Share.share({ message: JSON.stringify(data, null, 2) });
  }

  async function deleteAll() {
    const ok = await run(api.deleteMe);
    if (!ok) return;
    await stopNotifying();
    await forget();
    setOpen(null);
    setReply(null);
    setPlace('verify');
  }

  const tabs = {
    onMap: () => showMap(area),
    onTalk: () => talk('voice'),
    onYou: showYou,
  };

  if (!fontsReady) return <View style={{ flex: 1, backgroundColor: C.ground }} />;
  if (place === 'boot') {
    // Nothing loaded yet and the server can't be reached: say so instead of a black screen.
    return error ? (
      <SafeAreaProvider>
        <Problem title={copy.offline} body={copy.offlineBody} action={copy.retry} onAction={() => retry?.()} />
      </SafeAreaProvider>
    ) : (
      <View style={{ flex: 1, backgroundColor: C.ground }} />
    );
  }

  const white = place === 'talk' && reply?.theme === 'white' && !source;
  const sample = open?.sample ?? true;
  const refused = {
    minor: { title: copy.notEligibleTitle, body: copy.notEligibleBody, action: copy.back },
    failed: { title: copy.verifyFailedTitle, body: copy.verifyFailedBody, action: copy.retry },
    offline: { title: copy.offline, body: copy.offlineBody, action: copy.retry },
  }[refusal];

  return (
    <SafeAreaProvider>
      <StatusBar style={white ? 'dark' : 'light'} />
      {place === 'verify' && <Verify copy={copy} busy={busy} onVerify={verify} />}
      {place === 'refused' && <Problem {...refused} onAction={() => setPlace('verify')} />}
      {place === 'consent' && <Consent copy={copy} busy={busy} onAgree={agree} />}
      {place === 'home' && open && (
        <Home copy={copy} open={open} onTalk={() => talkFromHome('voice')} onType={() => talkFromHome('type')} onMap={tabs.onMap} onYou={showYou} />
      )}
      {place === 'talk' && reply && (
        <Talk
          key={reply.conversation_id}
          copy={copy}
          lang={lang}
          sample={sample}
          reply={reply}
          heard={heard}
          unlocked={open?.unlocked ?? false}
          busy={busy}
          error={error}
          startWith={startWith}
          onSay={say}
          onFix={fix}
          onReport={report}
          onSource={openSource}
          onRetry={() => retry?.()}
          onMap={tabs.onMap}
          onYou={showYou}
        />
      )}
      {place === 'map' && (
        <MapScreen
          copy={copy}
          data={map}
          sample={sample}
          area={area}
          preview={open?.preview ?? false}
          onArea={showMap}
          onTopic={openTopic}
          {...tabs}
        />
      )}
      {place === 'you' && (
        <YouScreen
          copy={copy}
          lang={lang}
          data={you}
          sample={sample}
          onAgreement={showAgreement}
          onLanguage={switchLanguage}
          onExport={exportData}
          onDelete={deleteAll}
          notifications={open?.notifications ?? false}
          onNotifications={setNotifications}
          preview={open?.preview ?? false}
          anonymous={open?.anonymous ?? true}
          name={open?.display_name ?? null}
          onAnonymous={setAnonymous}
          onWithdraw={withdraw}
          {...tabs}
        />
      )}
      {place === 'agreement' && (
        <AgreementScreen copy={copy} lang={lang} card={card} sample={sample} onAsk={askToSend} onSign={sign} {...tabs} />
      )}
      {source && (
        <View style={StyleSheet.absoluteFill}>
          <SourceScreen copy={copy} fact={source.fact} base={source.base} onBack={() => setSource(null)} />
        </View>
      )}
      {asking && (
        <View style={StyleSheet.absoluteFill}>
          <NotifyAsk copy={copy} onYes={notifyYes} onNo={() => setAsking(false)} />
        </View>
      )}
      {/* Talk shows errors in place. Everywhere else gets this strip. */}
      {error && place !== 'talk' && (
        <ErrorStrip
          text={error}
          retry={retry ? copy.retry : copy.cancel}
          onPress={() => {
            setError(null);
            retry?.();
          }}
        />
      )}
    </SafeAreaProvider>
  );
}

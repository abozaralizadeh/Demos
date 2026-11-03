# Demos: roadmap

What's built and what's next on the code side. How it should work is in [CONCEPT.md](CONCEPT.md), [DESIGN.md](DESIGN.md) and [LOGICAL-FLOW.md](LOGICAL-FLOW.md).

Everything runs on sample data for now. Facts about Milan are placeholders like `[SOURCE NAME]` until real, reviewed sources replace them.

## The talk engine

- [x] All thresholds in one config file
- [x] Next-move rules
- [x] Evidence packs
- [x] A model layer, so the model can be swapped
- [x] Number slots, so code writes every number
- [x] Reply checks and the fallback line
- [x] Handling the model declining or going down
- [x] Claim extraction and scrubbing of identifying details
- [x] Mirror and stance states
- [x] The "not enough of us yet" path
- [ ] Argument merging and fair rewriting
- [ ] The safety path, with the wording checked by experts
- [ ] A plain web test page with voice and captions

## The phone app

- [x] App shell, navigation and the mic as the Talk tab
- [x] Type instead
- [x] Consent screen, with consent text versions saved
- [x] AI label on talk screens
- [x] All talk screens, including the white flip on Challenge
- [x] Source detail
- [x] "Not enough of us yet"
- [x] You: what you believe
- [x] Settings: language, notifications, export, withdraw consent, delete
- [x] Report this reply
- [x] The World speaks first: all four kinds
- [x] Notifications: opt-in, once a day at most, local only, with no views in the text
- [x] Error screens: under 18, verification failed, mic denied, no network
- [ ] Mic capture tested on real phones, live captions, voice playback and mute
- [ ] "Speech failed" tested on a real phone
- [ ] Safety card help line numbers checked by experts
- [ ] Real identity verification instead of the dev stub

## The backend

- [x] The identity service, the vault and the keyed hash
- [x] Delete and export from end to end
- [x] `setup_service.sh`, which installs, updates and restarts all services
- [x] systemd services for api, worker and identity
- [x] Size-limited rotating log files
- [ ] Keep only what's needed from the identity check
- [ ] Sign-in sessions and the live WebSocket
- [ ] Retention jobs for transcripts and logs
- [ ] Review console: reports, arguments, facts, audits
- [ ] Encrypted nightly backups
- [ ] Monitoring and alerts

## Map, Agreements and the community

- [x] Map: bubbles, gaps and lines for one city
- [x] Map: Italy and World views (behind `DEMOS_PREVIEW_FEATURES`)
- [x] Named petitions on Agreement cards, as a prototype (behind `DEMOS_PREVIEW_FEATURES`)
- [ ] Topic link calculation
- [ ] Opinion groups and life groups
- [ ] Your words travel, Open mind and Bridges
- [ ] Agreement rules and snapshots
- [ ] Agreement cards and public web pages
- [ ] Send requests and the human review step
- [ ] New topic proposals
- [ ] Election pause and calendar
- [ ] Surge and coordination alerts
- [ ] Area filters and more languages

## Accessibility

- [ ] Screen reader support on iPhone and Android
- [ ] Reduced motion
- [ ] Large text
- [ ] Meet WCAG 2.2 AA

## Testing

- [x] Backend tests against a real Postgres
- [ ] Italian and English test sets from labelled talks
- [ ] Extraction accuracy against human labels
- [ ] Mirror-image tests: swap the person's side and check the World is equally tough
- [ ] Attack tests: spoken instructions, hate, attempts to make it invent numbers
- [ ] Speech services compared on real Italian voices, accents and noisy rooms
- [ ] A full backup restore
- [ ] A load test for 10,000 people

## Before every release

- [ ] Mirror-image fairness tests pass
- [ ] Attack tests pass
- [ ] The reply check failure rate is within limits
- [ ] Safety path tests pass

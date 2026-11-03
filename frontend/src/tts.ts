// Read-aloud. Screens call speak()/useTts() and never a speech engine directly, so a server-side
// provider (e.g. a Bhashini TTS proxy on our API: keys must stay on the server, never in the browser)
// can replace or back up the Web Speech API by calling setTtsProvider().
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { langInfo } from "./i18n/languages";

export interface TtsProvider {
  readonly name: string;
  /** Whether this provider can speak the app language `lang` right now. */
  canSpeak(lang: string): boolean;
  /** Speak `text`; resolves when done or stopped. */
  speak(text: string, lang: string): Promise<void>;
  stop(): void;
  /** Availability can change (browsers load voices late). */
  subscribe(cb: () => void): () => void;
}

const norm = (tag: string) => tag.replace(/_/g, "-").toLowerCase();

/** Web Speech API with the device's own voices. Hidden for languages without a voice. */
export class WebSpeechTts implements TtsProvider {
  readonly name = "web-speech";
  private voices: SpeechSynthesisVoice[] = [];
  private listeners = new Set<() => void>();

  constructor() {
    if (!this.supported()) return;
    const load = () => {
      this.voices = window.speechSynthesis.getVoices();
      this.listeners.forEach((l) => l());
    };
    load();
    window.speechSynthesis.addEventListener?.("voiceschanged", load);
  }

  private supported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  }

  /** Best voice for an app language: exact BCP-47 tag first (hi-IN), then the same primary language. */
  voiceFor(lang: string): SpeechSynthesisVoice | null {
    if (!this.voices.length) return null;
    const tags = langInfo(lang).bcp47.map(norm);
    for (const tag of tags) {
      const exact = this.voices.find((v) => norm(v.lang) === tag);
      if (exact) return exact;
    }
    const primaries = new Set(tags.map((t) => t.split("-")[0]));
    return this.voices.find((v) => primaries.has(norm(v.lang).split("-")[0])) ?? null;
  }

  canSpeak(lang: string): boolean {
    return this.supported() && this.voiceFor(lang) !== null;
  }

  speak(text: string, lang: string): Promise<void> {
    const voice = this.voiceFor(lang);
    if (!voice || !text.trim()) return Promise.resolve();
    const synth = window.speechSynthesis;
    synth.cancel();
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(text);
      u.voice = voice;
      u.lang = voice.lang;
      u.rate = 0.9;
      u.onend = () => resolve();
      u.onerror = () => resolve();
      synth.speak(u);
    });
  }

  stop(): void {
    if (this.supported()) window.speechSynthesis.cancel();
  }

  subscribe(cb: () => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }
}

let provider: TtsProvider = new WebSpeechTts();
let version = 0;
const providerListeners = new Set<() => void>();

export function setTtsProvider(p: TtsProvider): void {
  provider.stop();
  provider = p;
  version++;
  providerListeners.forEach((l) => l());
}

export function speak(text: string, lang: string): Promise<void> {
  return provider.speak(text, lang);
}

export function stopSpeaking(): void {
  provider.stop();
}

function subscribeAll(cb: () => void): () => void {
  providerListeners.add(cb);
  let inner = provider.subscribe(cb);
  const onProvider = () => {
    inner();
    inner = provider.subscribe(cb);
  };
  providerListeners.add(onProvider);
  return () => {
    inner();
    providerListeners.delete(cb);
    providerListeners.delete(onProvider);
  };
}

/** Read-aloud for one language: `available` is false when no voice exists (hide the button then). */
export function useTts(lang: string) {
  const available = useSyncExternalStore(
    subscribeAll,
    () => `${version}:${provider.canSpeak(lang)}`,
    () => "0:false",
  ).endsWith("true");
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => provider.stop(), []);
  const say = useCallback(
    async (text: string) => {
      setSpeaking(true);
      try {
        await provider.speak(text, lang);
      } finally {
        setSpeaking(false);
      }
    },
    [lang],
  );
  const stop = useCallback(() => {
    provider.stop();
    setSpeaking(false);
  }, []);
  return { available, speaking, speak: say, stop };
}

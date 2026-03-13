#!/usr/bin/env python3
"""
Pipeline Benchmark: STT → LLM → TTS

Measures the latency of each stage using the real service implementations.

Usage:
    python scripts/benchmark_voice_pipeline.py [--runs N] [--wav PATH] [--lang de|en]

Metrics captured per run:
  STT  — time from first audio chunk sent  → first FINAL transcript
  LLM  — time from sending transcript      → first text token  (TTFT)
         time from sending transcript      → full response complete
  TTS  — time from sending LLM response    → first audio chunk
         time from sending LLM response    → full audio complete
  E2E* — STT + LLM-TTFT + TTS-first-chunk (perceived start-of-speech latency)
"""

import argparse
import asyncio
import logging
import os
import sys
import time
import warnings
import wave
from pathlib import Path
from statistics import mean, median, stdev

# ── silence warnings from all sources ───────────────────────────────────────
# 1. Python warnings machinery (DeprecationWarning, ResourceWarning, UserWarning)
warnings.simplefilter("ignore")

# 2. gRPC / absl C-level messages and langchain DeprecationWarnings are written
#    directly to stderr and cannot be suppressed via Python's warnings module.
#    All benchmark output goes to stdout (print()), so we redirect stderr to
#    /dev/null for the entire process lifetime.  Genuine exceptions are caught
#    and re-routed to stdout below.
_devnull = open(os.devnull, "w")
sys.stderr = _devnull

# 3. gRPC verbosity (controls grpc_init / fork handler messages)
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GRPC_TRACE", "")

import numpy as np

# ── project path ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from ai_assistant.services.speech_to_text_service import SpeechToTextService
from ai_assistant.services.llm_service import LLMService
from ai_assistant.services.text_to_speech_service import TextToSpeechService
from ai_assistant.services.tts_playback_manager import SentenceParser
from ai_assistant.prompts_templates import (
    TRIAGE_CONVERSATION_PROMPT,
    get_language_instruction,
)
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)

# 4. absl-py logging (controls gRPC "I0000…" info lines).
try:
    from absl import logging as _absl_logging
    _absl_logging.set_verbosity(_absl_logging.ERROR)
except ImportError:
    pass

# 5. Silence all verbose third-party loggers — benchmark output is via print().
for _lib in ("google", "langchain", "langchain_core", "langchain_community",
             "httpx", "aiohttp", "urllib3", "grpc", "aioice"):
    logging.getLogger(_lib).setLevel(logging.CRITICAL)

# ── constants ────────────────────────────────────────────────────────────────
DEFAULT_WAV = ROOT / "tests/data/ai_assistant_test_input.wav"
STT_SAMPLE_RATE = 8_000   # what SpeechToTextService expects
CHUNK_BYTES     = 160      # 10 ms of 16-bit mono @ 8 kHz (80 samples × 2 bytes = 160)

LANGUAGE_CONFIG = {
    "de": {
        "language_code": os.getenv("LANGUAGE_CODE_DE", "de-DE"),
        "voice_name":    os.getenv("VOICE_NAME_DE",    "de-DE-Chirp3-HD-Sulafat"),
    },
    "en": {
        "language_code": os.getenv("LANGUAGE_CODE_EN", "en-US"),
        "voice_name":    os.getenv("VOICE_NAME_EN",    "en-US-Chirp3-HD-Sulafat"),
    },
}


# ── helpers ──────────────────────────────────────────────────────────────────

def load_wav_as_pcm(path: Path, target_rate: int = STT_SAMPLE_RATE) -> bytes:
    """Load a WAV file as raw 16-bit mono PCM, resampling to *target_rate*."""
    with wave.open(str(path)) as wf:
        source_rate = wf.getframerate()
        channels    = wf.getnchannels()
        raw         = wf.readframes(wf.getnframes())

    # Convert to float32 numpy array
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

    # Mix down to mono if needed
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    # Resample via linear interpolation
    if source_rate != target_rate:
        num_target = int(len(samples) * target_rate / source_rate)
        x_src = np.linspace(0, len(samples) - 1, len(samples))
        x_dst = np.linspace(0, len(samples) - 1, num_target)
        samples = np.interp(x_dst, x_src, samples)

    # Clip and convert back to int16 PCM
    samples = np.clip(samples, -32768, 32767).astype(np.int16)
    return samples.tobytes()


async def _audio_gen(pcm: bytes, chunk: int = CHUNK_BYTES):
    """Async generator that yields PCM chunks as fast as possible."""
    for i in range(0, len(pcm), chunk):
        yield pcm[i:i + chunk]


def _triage_prompt(lang: str) -> ChatPromptTemplate:
    # Embed the static variables directly so the chain only needs {input}/{history}.
    system = (
        TRIAGE_CONVERSATION_PROMPT
        .replace("{agent_name}", "Elin")
        .replace("{user_name}",   "Benchmark User")
        .replace("{language_instruction}", get_language_instruction(lang))
    )
    return ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])


def _fmt(seconds: float) -> str:
    return f"{seconds * 1000:.0f} ms"


# ── single-run benchmark ─────────────────────────────────────────────────────

async def run_once(
    stt: SpeechToTextService,
    llm: LLMService,
    tts: TextToSpeechService,
    pcm: bytes,
    lang: str,
    run_index: int,
) -> dict:
    session_id = f"benchmark-{run_index}-{int(time.time())}"
    prompt_tmpl = _triage_prompt(lang)

    # ── STT ──────────────────────────────────────────────────────────────────
    stt_start      = time.perf_counter()
    stt_first_final = None
    transcript      = ""

    async for text, is_final in stt.continuous_stream(_audio_gen(pcm)):
        if is_final and stt_first_final is None:
            stt_first_final = time.perf_counter() - stt_start
            transcript = text
            break   # one final is enough — mirrors real VAD behaviour

    stt_elapsed = time.perf_counter() - stt_start
    if not transcript:
        print(f"  [run {run_index}] ⚠️  STT returned no final transcript — skipping run")
        return {}

    print(f"  [run {run_index}] STT  → '{transcript[:60]}{'…' if len(transcript)>60 else ''}'  ({_fmt(stt_first_final)})")

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_start       = time.perf_counter()
    llm_ttft        = None
    llm_full        = ""

    async for chunk in llm.generate_stream(transcript, prompt_tmpl, session_id):
        if isinstance(chunk, str) and chunk:
            if llm_ttft is None:
                llm_ttft = time.perf_counter() - llm_start
            llm_full += chunk

    llm_elapsed = time.perf_counter() - llm_start

    print(f"  [run {run_index}] LLM  → TTFT {_fmt(llm_ttft)}, total {_fmt(llm_elapsed)}")
    print(f"             response: '{llm_full[:80]}{'…' if len(llm_full)>80 else ''}'")

    # ── TTS ──────────────────────────────────────────────────────────────────
    # Mirror the production path: split LLM response into sentences using the
    # same SentenceParser used by TTSPlaybackManager, synthesize all sentences
    # concurrently, and report the first-chunk latency of the first sentence
    # (= perceived start-of-speech latency).
    sentences = SentenceParser.split_into_sentences(llm_full)
    if not sentences:
        sentences = [llm_full]

    tts_start       = time.perf_counter()
    tts_first_chunk = None
    tts_total_bytes = 0

    async def _synthesize_sentence(sentence: str) -> tuple[float | None, int]:
        """Synthesize one sentence; return (first_chunk_latency, total_bytes)."""
        first = None
        nbytes = 0
        async for chunk in tts.synthesize_stream(sentence):
            if chunk:
                if first is None:
                    first = time.perf_counter() - tts_start
                nbytes += len(chunk)
        return first, nbytes

    # Synthesize all sentences concurrently — same as production.
    tts_results = await asyncio.gather(*(_synthesize_sentence(s) for s in sentences))

    for first, nbytes in tts_results:
        tts_total_bytes += nbytes
        if first is not None and (tts_first_chunk is None or first < tts_first_chunk):
            tts_first_chunk = first

    tts_elapsed = time.perf_counter() - tts_start
    print(f"  [run {run_index}] TTS  → first chunk {_fmt(tts_first_chunk)}, total {_fmt(tts_elapsed)} "
          f"({tts_total_bytes//1024} KB, {len(sentences)} sentence(s))")

    e2e = stt_first_final + llm_ttft + tts_first_chunk
    print(f"  [run {run_index}] E2E* → {_fmt(e2e)}  (STT→FINAL + LLM→TTFT + TTS→first chunk)\n")

    return {
        "stt_final":       stt_first_final,
        "llm_ttft":        llm_ttft,
        "llm_total":       llm_elapsed,
        "tts_first_chunk": tts_first_chunk,
        "tts_total":       tts_elapsed,
        "e2e":             e2e,
        "transcript":      transcript,
    }


# ── summary ───────────────────────────────────────────────────────────────────

def print_summary(results: list[dict]) -> None:
    if not results:
        print("No results to summarise.")
        return

    keys = ["stt_final", "llm_ttft", "llm_total", "tts_first_chunk", "tts_total", "e2e"]
    labels = {
        "stt_final":       "STT  → first FINAL",
        "llm_ttft":        "LLM  → TTFT",
        "llm_total":       "LLM  → total",
        "tts_first_chunk": "TTS  → first chunk",
        "tts_total":       "TTS  → total",
        "e2e":             "E2E* → perceived start",
    }

    print("=" * 58)
    print(f"  SUMMARY  ({len(results)} run{'s' if len(results)>1 else ''})")
    print("=" * 58)
    for k in keys:
        vals = [r[k] for r in results]
        m = mean(vals)
        med = median(vals)
        sd = stdev(vals) if len(vals) > 1 else 0.0
        print(f"  {labels[k]:<24}  avg {_fmt(m):>8}  med {_fmt(med):>8}  σ {_fmt(sd):>7}")
    print("=" * 58)


# ── main ──────────────────────────────────────────────────────────────────────

async def main(runs: int, wav_path: Path, lang: str) -> None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("❌  GEMINI_API_KEY is not set in .env")

    cfg = LANGUAGE_CONFIG.get(lang, LANGUAGE_CONFIG["de"])
    print(f"\n🔧 Config: lang={lang}, voice={cfg['voice_name']}")
    print(f"📂 WAV:    {wav_path}\n")

    print("Loading and resampling audio... ", end="", flush=True)
    pcm = load_wav_as_pcm(wav_path)
    duration_s = len(pcm) / 2 / STT_SAMPLE_RATE
    print(f"{len(pcm)//1024} KB  ({duration_s:.2f}s @ {STT_SAMPLE_RATE//1000}kHz mono 16-bit)")

    stt = SpeechToTextService(language_code=cfg["language_code"])
    llm = LLMService(api_key=api_key, model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"))
    tts = TextToSpeechService(language_code=cfg["language_code"], voice_name=cfg["voice_name"])

    results = []
    for i in range(1, runs + 1):
        print(f"── Run {i}/{runs} " + "─" * 38)
        result = await run_once(stt, llm, tts, pcm, lang, i)
        if result:
            results.append(result)
        if i < runs:
            await asyncio.sleep(1)   # brief pause between runs to avoid rate limits

    print()
    print_summary(results)

    # Close async clients to prevent ResourceWarning on exit
    await stt.client.transport.close()
    await tts.client.transport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark STT → LLM → TTS pipeline")
    parser.add_argument("--runs", type=int, default=3,    help="Number of benchmark runs (default: 3)")
    parser.add_argument("--wav",  type=Path, default=DEFAULT_WAV, help="Path to input WAV file")
    parser.add_argument("--lang", choices=["de", "en"], default="de", help="Language (default: de)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.runs, args.wav, args.lang))
    except Exception as exc:
        # stderr is silenced; route fatal errors to stdout so they're visible.
        print(f"\n❌  Fatal error: {exc}", flush=True)
        sys.exit(1)

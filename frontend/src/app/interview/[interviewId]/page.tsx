"use client";

import { Mic, Square, Waves } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AnswerScore, InterviewQuestion } from "@/lib/types";
import { formatScore, titleCase } from "@/lib/utils";

interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): { transcript: string };
  [index: number]: { transcript: string };
}

interface SpeechRecognitionEventLike extends Event {
  readonly resultIndex: number;
  readonly results: ArrayLike<SpeechRecognitionResultLike>;
}

interface BrowserSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: Event & { error?: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

export default function InterviewSessionPage() {
  const params = useParams<{ interviewId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const interviewId = params.interviewId;
  const accessToken = searchParams.get("access");
  const [currentQuestion, setCurrentQuestion] = useState<InterviewQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [lastScore, setLastScore] = useState<AnswerScore | null>(null);
  const [booting, setBooting] = useState(true);
  const [interviewMode, setInterviewMode] = useState("text");
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [audioPreviewUrl, setAudioPreviewUrl] = useState<string | null>(null);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const timerRef = useRef<number | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const previewUrlRef = useRef<string | null>(null);

  useEffect(() => {
    const initialize = async () => {
      const interview = await api.startInterview(interviewId, accessToken);
      setInterviewMode(interview.mode);
      const next = await api.getNextQuestion(interviewId, accessToken);
      if ("done" in next) {
        const report = await api.completeInterview(interviewId, accessToken);
        router.replace(`/interview/${interviewId}/complete?reportId=${report.id}`);
        return;
      }
      setCurrentQuestion(next);
      setBooting(false);
    };

    initialize().catch((error) => {
      setSessionError(error instanceof Error ? error.message : "We could not validate this interview link.");
      setBooting(false);
    });
  }, [accessToken, interviewId, router]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
      }
      recognitionRef.current?.abort();
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  const stopVoiceSession = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    recorderRef.current?.stop();
    recorderRef.current = null;
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setIsRecording(false);
  };

  const startVoiceSession = async () => {
    setRecordingError(null);
    setTranscriptDraft("");
    setRecordingSeconds(0);
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
      setAudioPreviewUrl(null);
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setRecordingError("This browser does not support microphone capture.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };
      recorder.onstop = () => {
        if (!chunks.length) {
          return;
        }
        const previewUrl = URL.createObjectURL(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
        previewUrlRef.current = previewUrl;
        setAudioPreviewUrl(previewUrl);
      };
      recorder.start(250);

      startedAtRef.current = Date.now();
      timerRef.current = window.setInterval(() => {
        setRecordingSeconds(Math.round((Date.now() - (startedAtRef.current || Date.now())) / 1000));
      }, 1000);

      const speechWindow = window as Window & {
        SpeechRecognition?: SpeechRecognitionConstructor;
        webkitSpeechRecognition?: SpeechRecognitionConstructor;
      };
      const RecognitionCtor =
        speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
      setSpeechSupported(Boolean(RecognitionCtor));

      if (RecognitionCtor) {
        const recognition = new RecognitionCtor();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";
        recognition.onresult = (event) => {
          const segments: string[] = [];
          for (let index = 0; index < event.results.length; index += 1) {
            const part = event.results[index]?.item(0)?.transcript || event.results[index]?.[0]?.transcript;
            if (part) {
              segments.push(part.trim());
            }
          }
          setTranscriptDraft(segments.join(" ").trim());
        };
        recognition.onerror = (event) => {
          setRecordingError(
            event.error
              ? `Automatic transcription paused: ${event.error}. You can still edit the transcript manually.`
              : "Automatic transcription paused. You can still edit the transcript manually.",
          );
        };
        recognition.start();
        recognitionRef.current = recognition;
      } else {
        setRecordingError(
          "Live browser transcription is not available here. You can still record and type or paste the transcript before submitting.",
        );
      }

      setIsRecording(true);
    } catch (error) {
      setRecordingError(
        error instanceof Error
          ? error.message
          : "We could not access the microphone for this interview.",
      );
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };

  const answerMutation = useMutation({
    mutationFn: async () => {
      if (!currentQuestion) {
        throw new Error("Question not loaded");
      }
      const preparedText =
        interviewMode === "voice" ? transcriptDraft.trim() : answer.trim();
      const result = await api.submitAnswer(interviewId, {
        question_id: currentQuestion.id,
        answer_text: preparedText,
        answer_mode: interviewMode,
        transcript_text: interviewMode === "voice" ? preparedText : null,
        latency_ms: interviewMode === "voice" ? recordingSeconds * 1000 : 0,
        access_token: accessToken,
      });
      const next = await api.getNextQuestion(interviewId, accessToken);
      return { result, next };
    },
    onSuccess: async ({ result, next }) => {
      setLastScore(result.score);
      setAnswer("");
      setTranscriptDraft("");
      setRecordingSeconds(0);
      setRecordingError(null);
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
      }
      setAudioPreviewUrl(null);
      if ("done" in next) {
        const report = await api.completeInterview(interviewId, accessToken);
        router.replace(`/interview/${interviewId}/complete?reportId=${report.id}`);
        return;
      }
      setCurrentQuestion(next);
    },
  });

  if (booting) {
    return (
      <div className="flex min-h-screen items-center justify-center px-5">
        <div className="glass rounded-[28px] border border-border bg-surface px-6 py-4 text-sm text-muted">
          Preparing your interview session...
        </div>
      </div>
    );
  }

  if (sessionError) {
    return (
      <div className="flex min-h-screen items-center justify-center px-5 py-8">
        <Card className="w-full max-w-2xl text-center">
          <h1 className="font-display text-4xl font-semibold text-text">Interview link unavailable</h1>
          <p className="mt-4 text-sm leading-7 text-muted">
            {sessionError}
          </p>
          <p className="mt-3 text-sm leading-7 text-muted">
            Ask your recruiter for a fresh HireOS invite link if this one was replaced, revoked, or expired.
          </p>
        </Card>
      </div>
    );
  }

  const submitDisabled =
    answerMutation.isPending ||
    (interviewMode === "voice" ? !transcriptDraft.trim() : !answer.trim());

  return (
    <div className="flex min-h-screen items-center justify-center px-5 py-8">
      <div className="w-full max-w-4xl space-y-5">
        <Card className="bg-[#15222d] text-white">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Badge tone="brand" className="bg-white/12 text-white">
              HireOS AI Interview
            </Badge>
            <Badge tone="neutral" className="bg-white/12 text-white">
              {titleCase(interviewMode)} mode
            </Badge>
          </div>
          <h1 className="mt-5 font-display text-4xl font-semibold">
            Candidate screening session
          </h1>
          <p className="mt-4 text-sm leading-7 text-slate-300">
            This interview is AI-assisted. Your responses are used to generate recruiter decision-support signals and will be reviewed by a human.
          </p>
        </Card>

        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm uppercase tracking-[0.22em] text-brand">
                Question {currentQuestion?.question_order}
              </p>
              <p className="mt-2 text-sm leading-7 text-muted">
                Skill category: {currentQuestion?.skill_category}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone="neutral">{currentQuestion?.difficulty}</Badge>
              {interviewMode === "voice" ? (
                <Badge tone={isRecording ? "warning" : "brand"}>
                  {isRecording ? `Recording ${recordingSeconds}s` : "Ready for voice"}
                </Badge>
              ) : null}
            </div>
          </div>

          <h2 className="mt-4 font-display text-3xl font-semibold text-text">
            {currentQuestion?.question_text}
          </h2>

          {interviewMode === "voice" ? (
            <div className="mt-6 space-y-4">
              <div className="grid gap-4 rounded-[24px] border border-border bg-white/70 px-4 py-4 md:grid-cols-[1fr_auto] md:items-center">
                <div>
                  <p className="text-sm font-semibold text-text">
                    Record your answer and review the transcript before scoring.
                  </p>
                  <p className="mt-2 text-sm leading-7 text-muted">
                    Browser transcription {speechSupported ? "is active for this session." : "may vary by browser."} You can always edit the transcript manually before submission.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  {!isRecording ? (
                    <button
                      type="button"
                      onClick={() => startVoiceSession()}
                      className="inline-flex items-center gap-2 rounded-full bg-brand px-5 py-3 text-sm font-semibold text-white"
                    >
                      <Mic className="size-4" />
                      Start recording
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => stopVoiceSession()}
                      className="inline-flex items-center gap-2 rounded-full bg-rose-600 px-5 py-3 text-sm font-semibold text-white"
                    >
                      <Square className="size-4" />
                      Stop recording
                    </button>
                  )}
                </div>
              </div>

              {recordingError ? (
                <div className="rounded-[24px] bg-amber-50 px-4 py-4 text-sm text-amber-800">
                  {recordingError}
                </div>
              ) : null}

              {audioPreviewUrl ? (
                <div className="rounded-[24px] border border-border bg-white/70 px-4 py-4">
                  <div className="flex items-center gap-2 text-sm font-semibold text-text">
                    <Waves className="size-4 text-brand" />
                    Audio preview
                  </div>
                  <audio controls className="mt-4 w-full">
                    <source src={audioPreviewUrl} />
                  </audio>
                </div>
              ) : null}

              <div>
                <label className="text-sm font-medium text-muted">
                  Transcript review
                </label>
                <textarea
                  rows={8}
                  className="mt-2 w-full rounded-[24px] border border-border bg-white/80 px-4 py-4 outline-none"
                  placeholder="Your transcript will appear here. You can also paste or edit it manually before scoring."
                  value={transcriptDraft}
                  onChange={(event) => setTranscriptDraft(event.target.value)}
                />
              </div>
            </div>
          ) : (
            <textarea
              rows={8}
              className="mt-6 w-full rounded-[24px] border border-border bg-white/80 px-4 py-4 outline-none"
              placeholder="Type your answer here..."
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
            />
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted">
              {interviewMode === "voice"
                ? "Transcript-based scoring remains decision support and should be reviewed by a human recruiter."
                : "Typed answers are scored for concept coverage, clarity, and communication quality."}
            </p>
            <button
              type="button"
              disabled={submitDisabled}
              onClick={() => {
                if (isRecording) {
                  stopVoiceSession();
                }
                answerMutation.mutate();
              }}
              className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              {answerMutation.isPending ? "Scoring..." : "Submit answer"}
            </button>
          </div>
        </Card>

        {lastScore ? (
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-display text-2xl font-semibold text-text">
                Latest AI feedback
              </h3>
              <Badge tone={lastScore.total_score >= 70 ? "success" : "warning"}>
                {formatScore(lastScore.total_score)}%
              </Badge>
            </div>
            <p className="mt-4 text-sm leading-7 text-muted">{lastScore.explanation}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {lastScore.matched_concepts.map((concept) => (
                <Badge key={concept} tone="brand">
                  {concept}
                </Badge>
              ))}
            </div>
            {lastScore.weaknesses.length ? (
              <div className="mt-5 rounded-[24px] bg-amber-50 px-4 py-4 text-sm text-amber-800">
                {lastScore.weaknesses[0]}
                {lastScore.suggested_follow_up ? (
                  <p className="mt-2 text-amber-900">
                    Suggested follow-up: {lastScore.suggested_follow_up}
                  </p>
                ) : null}
              </div>
            ) : null}
          </Card>
        ) : null}
      </div>
    </div>
  );
}

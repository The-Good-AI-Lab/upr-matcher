import {
	AlertCircle,
	Clock,
	FileText,
	ListChecks,
	Loader2,
	Play,
	RefreshCw,
	Save,
	Sparkles,
} from "lucide-react";
import mammoth from "mammoth";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import logo from "@/assets/logo.svg";
import { DocumentUpload } from "@/components/DocumentUpload";
import { DocumentViewer } from "@/components/DocumentViewer";
import { DownloadButton } from "@/components/DownloadButton";
import { PdfViewer } from "@/components/PdfViewer";
import { PreviousRuns } from "@/components/PreviousRuns";
import {
	type Recommendation,
	RecommendationsTable,
} from "@/components/RecommendationsTable";
import { SummarySection } from "@/components/SummarySection";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
	analyzeDocuments,
	type FmsiSummary,
	fetchPrediction,
	fetchProgress,
	type JobSummary,
	submitFeedback,
	type UprSummary,
} from "@/lib/api";

interface UploadedFileDisplay {
	name: string;
	content: string;
	isHtml?: boolean;
	isPdf?: boolean;
	pdfUrl?: string;
	isDocx?: boolean;
	docxArrayBuffer?: ArrayBuffer;
}

const STORAGE_KEY = "urp_matcher_session";

interface PersistedSession {
	jobId?: string;
	predictionId?: string;
}

function saveSession(session: PersistedSession) {
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
	} catch {
		// storage quota exceeded or private browsing — ignore
	}
}

function clearSession() {
	try {
		localStorage.removeItem(STORAGE_KEY);
	} catch {
		// ignore
	}
}

function loadSession(): PersistedSession | null {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		return raw ? (JSON.parse(raw) as PersistedSession) : null;
	} catch {
		return null;
	}
}

const Index = () => {
	const [uploadedFile1, setUploadedFile1] =
		useState<UploadedFileDisplay | null>(null);
	const [uploadedFile2, setUploadedFile2] =
		useState<UploadedFileDisplay | null>(null);
	const [isDocument1Minimized, setIsDocument1Minimized] = useState(false);
	const [isDocument2Minimized, setIsDocument2Minimized] = useState(false);
	const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
	const [isAnalyzing, setIsAnalyzing] = useState(false);
	const [_sessionId, setSessionId] = useState<string | null>(null);
	const [uprSummary, setUprSummary] = useState<UprSummary | null>(null);
	const [fmsiSummary, setFmsiSummary] = useState<FmsiSummary | null>(null);
	const [analysisProgress, setAnalysisProgress] = useState(0);
	const [progressMessage, setProgressMessage] = useState(
		"Preparing analysis...",
	);
	const [jobStatus, setJobStatus] = useState<
		"idle" | "pending" | "processing" | "failed"
	>("idle");
	const [failureMessage, setFailureMessage] = useState<string | null>(null);
	const rawFile1Ref = useRef<File | null>(null);
	const rawFile2Ref = useRef<File | null>(null);
	const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(
		null,
	);
	const activeJobFilesRef = useRef<{ ref: File; src: File } | null>(null);
	const pollErrorCountRef = useRef(0);

	const stopProgressPolling = useCallback(() => {
		if (progressIntervalRef.current) {
			clearInterval(progressIntervalRef.current);
			progressIntervalRef.current = null;
		}
	}, []);

	const resetAnalysisState = useCallback(
		({
			status,
			message,
			failure,
		}: {
			status: "idle" | "failed";
			message: string;
			failure?: string | null;
		}) => {
			stopProgressPolling();
			setJobStatus(status);
			setProgressMessage(message);
			setFailureMessage(failure ?? null);
			setAnalysisProgress(0);
			setIsAnalyzing(false);
			clearSession();
		},
		[stopProgressPolling],
	);

	useEffect(() => {
		return () => {
			if (progressIntervalRef.current) {
				clearInterval(progressIntervalRef.current);
			}
		};
	}, []);

	const pollProgress = useCallback(
		async (jobId: string) => {
			try {
				const status = await fetchProgress(jobId);
				pollErrorCountRef.current = 0;
				setJobStatus(
					status.status === "pending" || status.status === "processing"
						? status.status
						: status.status === "failed"
							? "failed"
							: "idle",
				);
				setAnalysisProgress(status.percent);
				setProgressMessage(status.message);
				if (status.status === "completed") {
					stopProgressPolling();
					if (status.predictionId) {
						try {
							const files = activeJobFilesRef.current;
							const session = await fetchPrediction(
								status.predictionId,
								files?.ref.name,
								files?.src.name,
							);
							setSessionId(session.id);
							setRecommendations(session.recommendations);
							setUprSummary(session.uprSummary);
							setFmsiSummary(session.fmsiSummary);
							setAnalysisProgress(100);
							setProgressMessage("Analysis complete");
							setJobStatus("idle");
							saveSession({ predictionId: session.id });
							toast.success(
								`Analysis complete! Found ${session.recommendations.length} recommendation matches.`,
							);
						} catch (err) {
							console.error("Failed to load results:", err);
							toast.error("Analysis finished but failed to load results");
						}
					}
					setIsAnalyzing(false);
				} else if (status.status === "failed") {
					resetAnalysisState({
						status: "failed",
						message: status.message || "Analysis failed",
						failure: status.message || "Analysis failed",
					});
				} else if (status.status === "unknown") {
					resetAnalysisState({
						status: "idle",
						message: "No active analysis found",
					});
					toast.warning(
						"Previous queued run was not found. You can start a new analysis.",
					);
				}
			} catch (error) {
				console.error("Progress poll error:", error);
				pollErrorCountRef.current += 1;
				if (pollErrorCountRef.current >= 5) {
					stopProgressPolling();
					setFailureMessage(
						"Lost connection to the server. The job may still be running — check Previous Runs later.",
					);
					setJobStatus("failed");
					setIsAnalyzing(false);
					clearSession();
				}
			}
		},
		[resetAnalysisState, stopProgressPolling],
	);

	const startProgressPolling = useCallback(
		(jobId: string) => {
			stopProgressPolling();
			pollErrorCountRef.current = 0;
			setJobStatus("pending");
			setFailureMessage(null);
			setProgressMessage("Waiting in queue...");
			setAnalysisProgress(0);
			pollProgress(jobId);
			progressIntervalRef.current = setInterval(() => {
				pollProgress(jobId);
			}, 1000);
		},
		[pollProgress, stopProgressPolling],
	);

	// Restore previous session on mount — placed after polling functions are declared
	useEffect(() => {
		const session = loadSession();
		if (!session) return;

		if (session.predictionId) {
			fetchPrediction(session.predictionId)
				.then((s) => {
					setSessionId(s.id);
					setRecommendations(s.recommendations);
					setUprSummary(s.uprSummary);
					setFmsiSummary(s.fmsiSummary);
					toast.info("Previous results restored.");
				})
				.catch(() => {
					clearSession();
				});
		} else if (session.jobId) {
			setIsAnalyzing(true);
			startProgressPolling(session.jobId);
		}
	}, [startProgressPolling]);

	const progressStages = [
		{ threshold: 5, label: "Preparing", icon: FileText },
		{ threshold: 30, label: "Reading", icon: FileText },
		{ threshold: 55, label: "Comparing", icon: Sparkles },
		{ threshold: 70, label: "Prioritizing", icon: ListChecks },
		{ threshold: 85, label: "Summarizing", icon: Sparkles },
		{ threshold: 92, label: "Saving", icon: Save },
	];

	const handleAnalyze = async () => {
		if (!rawFile1Ref.current || !rawFile2Ref.current) {
			toast.error("Please upload both documents first");
			return;
		}

		const jobId =
			globalThis.crypto?.randomUUID?.() ??
			`${Date.now()}-${Math.random().toString(16).slice(2)}`;
		clearSession();
		setIsAnalyzing(true);
		setProgressMessage("Submitting job...");
		setAnalysisProgress(0);
		setRecommendations([]);
		setUprSummary(null);
		setFmsiSummary(null);
		setSessionId(null);
		activeJobFilesRef.current = {
			ref: rawFile1Ref.current,
			src: rawFile2Ref.current,
		};
		toast.info("Analyzing documents... This may take a moment.");

		try {
			await analyzeDocuments(rawFile1Ref.current, rawFile2Ref.current, jobId);
			saveSession({ jobId });
			startProgressPolling(jobId);
		} catch (error) {
			console.error("Analysis error:", error);
			const msg = error instanceof Error ? error.message : "Analysis failed";
			setFailureMessage(msg);
			setJobStatus("failed");
			setProgressMessage(msg);
			setAnalysisProgress(0);
			setIsAnalyzing(false);
		}
	};

	const handleFileUpload = (slot: 1 | 2) => async (file: File) => {
		try {
			const fileExtension = file.name.split(".").pop()?.toLowerCase();

			if (slot === 1) {
				rawFile1Ref.current = file;
			} else {
				rawFile2Ref.current = file;
			}

			let fileData: UploadedFileDisplay;

			if (fileExtension === "pdf") {
				const pdfUrl = URL.createObjectURL(file);
				fileData = {
					name: file.name,
					content: "",
					isPdf: true,
					pdfUrl: pdfUrl,
				};
				toast.success("PDF uploaded successfully");
			} else if (fileExtension === "docx" || fileExtension === "doc") {
				const arrayBuffer = await file.arrayBuffer();
				const result = await mammoth.convertToHtml({ arrayBuffer });
				fileData = {
					name: file.name,
					content: result.value,
					isHtml: true,
					isDocx: true,
					docxArrayBuffer: arrayBuffer,
				};
				toast.success("Document uploaded and rendered successfully");
			} else {
				const text = await file.text();
				fileData = {
					name: file.name,
					content: text,
					isHtml: false,
				};
				toast.success("Document uploaded successfully");
			}

			if (slot === 1) {
				setUploadedFile1(fileData);
				setIsDocument1Minimized(false);
			} else {
				setUploadedFile2(fileData);
				setIsDocument2Minimized(false);
			}
		} catch (error) {
			console.error("Document upload error:", error);
			toast.error("Failed to read document");
		}
	};

	const handleFeedback = async (
		matchId: string,
		matchEntryId: string,
		feedback: "correct" | "incorrect",
	) => {
		const currentRec = recommendations.find(
			(r) => r.matchEntryId === matchEntryId,
		);
		const newFeedback = currentRec?.feedback === feedback ? null : feedback;

		setRecommendations((prev) =>
			prev.map((rec) =>
				rec.matchEntryId === matchEntryId
					? { ...rec, feedback: newFeedback }
					: rec,
			),
		);

		try {
			await submitFeedback(matchId, matchEntryId, feedback);
		} catch (error) {
			console.error("Feedback error:", error);
			toast.error("Failed to submit feedback");
			setRecommendations((prev) =>
				prev.map((rec) =>
					rec.matchEntryId === matchEntryId
						? { ...rec, feedback: currentRec?.feedback }
						: rec,
				),
			);
		}
	};

	const handleDeleteFile = (slot: 1 | 2) => {
		if (slot === 1) {
			setUploadedFile1(null);
			setIsDocument1Minimized(false);
			rawFile1Ref.current = null;
		} else {
			setUploadedFile2(null);
			setIsDocument2Minimized(false);
			rawFile2Ref.current = null;
		}
		setRecommendations([]);
		setUprSummary(null);
		setFmsiSummary(null);
		setSessionId(null);
	};

	const handleLoadRun = async (job: JobSummary) => {
		if (!job.predictionId) return;
		try {
			const session = await fetchPrediction(job.predictionId);
			setSessionId(session.id);
			setRecommendations(session.recommendations);
			setUprSummary(session.uprSummary);
			setFmsiSummary(session.fmsiSummary);
			saveSession({ predictionId: session.id });
			toast.success(
				`Loaded run with ${session.recommendations.length} matches.`,
			);
		} catch {
			toast.error("Failed to load that run");
		}
	};

	return (
		<div className="min-h-screen bg-background">
			{/* Header */}
			<header className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-50">
				<div className="container mx-auto px-4 py-4">
					<div className="flex items-center gap-4">
						<img src={logo} alt="The Good AI Lab" className="h-12 w-auto" />
						<div>
							<h1 className="text-2xl font-bold text-foreground">
								UPR Matcher
							</h1>
							<p className="text-sm text-muted-foreground">
								Recommendation Analysis
							</p>
						</div>
						<div className="ml-auto">
							<PreviousRuns onLoadRun={handleLoadRun} />
						</div>
					</div>
				</div>
			</header>

			{/* Main Content */}
			<main className="container mx-auto px-4 py-8">
				<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
					{/* Source Document */}
					<div className="space-y-4">
						<h2 className="text-lg font-semibold text-foreground">
							Source Document
						</h2>
						{!uploadedFile2 || isDocument2Minimized ? (
							<DocumentUpload
								onFileUpload={handleFileUpload(2)}
								hasMinimizedFile={isDocument2Minimized && !!uploadedFile2}
								minimizedFileName={uploadedFile2?.name}
								onRestoreFile={() => setIsDocument2Minimized(false)}
								onDeleteFile={() => handleDeleteFile(2)}
								description="Supports PDF files"
								accept=".pdf"
							/>
						) : uploadedFile2.isPdf && uploadedFile2.pdfUrl ? (
							<PdfViewer
								fileName={uploadedFile2.name}
								fileUrl={uploadedFile2.pdfUrl}
								onMinimize={() => setIsDocument2Minimized(true)}
								onDelete={() => handleDeleteFile(2)}
							/>
						) : (
							<DocumentViewer
								fileName={uploadedFile2.name}
								content={uploadedFile2.content}
								isHtml={uploadedFile2.isHtml}
								isDocx={uploadedFile2.isDocx}
								docxArrayBuffer={uploadedFile2.docxArrayBuffer}
								onMinimize={() => setIsDocument2Minimized(true)}
								onDelete={() => handleDeleteFile(2)}
							/>
						)}
					</div>

					{/* UPR Document */}
					<div className="space-y-4">
						<h2 className="text-lg font-semibold text-foreground">
							UPR Document
						</h2>
						{!uploadedFile1 || isDocument1Minimized ? (
							<DocumentUpload
								onFileUpload={handleFileUpload(1)}
								hasMinimizedFile={isDocument1Minimized && !!uploadedFile1}
								minimizedFileName={uploadedFile1?.name}
								onRestoreFile={() => setIsDocument1Minimized(false)}
								onDeleteFile={() => handleDeleteFile(1)}
								description="Supports DOCX files"
								accept=".docx"
							/>
						) : uploadedFile1.isPdf && uploadedFile1.pdfUrl ? (
							<PdfViewer
								fileName={uploadedFile1.name}
								fileUrl={uploadedFile1.pdfUrl}
								onMinimize={() => setIsDocument1Minimized(true)}
								onDelete={() => handleDeleteFile(1)}
							/>
						) : (
							<DocumentViewer
								fileName={uploadedFile1.name}
								content={uploadedFile1.content}
								isHtml={uploadedFile1.isHtml}
								isDocx={uploadedFile1.isDocx}
								docxArrayBuffer={uploadedFile1.docxArrayBuffer}
								onMinimize={() => setIsDocument1Minimized(true)}
								onDelete={() => handleDeleteFile(1)}
							/>
						)}
					</div>
				</div>

				{/* Analyze Button */}
				<div className="flex justify-center mb-6">
					<Button
						onClick={handleAnalyze}
						disabled={!uploadedFile1 || !uploadedFile2 || isAnalyzing}
						size="lg"
						className="w-full md:w-auto"
					>
						{isAnalyzing ? (
							<>
								<Loader2 className="h-5 w-5 mr-2 animate-spin" />
								Analyzing Documents...
							</>
						) : (
							<>
								<Play className="h-5 w-5 mr-2" />
								Analyze Documents
							</>
						)}
					</Button>
				</div>

				{jobStatus === "failed" && failureMessage && (
					<Card className="mb-6 p-4 bg-destructive/10 border-destructive/30">
						<div className="flex items-start gap-3">
							<AlertCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
							<div className="flex-1 min-w-0">
								<p className="text-sm font-semibold text-destructive">
									Analysis failed
								</p>
								<p className="text-xs text-muted-foreground mt-0.5 break-words">
									{failureMessage}
								</p>
							</div>
							<Button
								variant="outline"
								size="sm"
								className="shrink-0 border-destructive/40 text-destructive hover:bg-destructive/10"
								onClick={handleAnalyze}
							>
								<RefreshCw className="h-3.5 w-3.5 mr-1.5" />
								Retry
							</Button>
						</div>
					</Card>
				)}

				{jobStatus === "pending" && isAnalyzing && (
					<Card className="mb-6 p-4 bg-muted/40 border-muted-foreground/20">
						<div className="flex items-center gap-3">
							<Clock className="h-5 w-5 text-muted-foreground animate-pulse shrink-0" />
							<div className="flex-1">
								<p className="text-sm font-semibold text-foreground">
									Waiting in queue
								</p>
								<p className="text-xs text-muted-foreground">
									Your job is queued and will start shortly.
								</p>
							</div>
							<Loader2 className="h-4 w-4 text-muted-foreground animate-spin shrink-0" />
						</div>
					</Card>
				)}

				{(isAnalyzing || analysisProgress > 0) &&
					jobStatus !== "pending" &&
					jobStatus !== "failed" && (
						<Card
							className={`mb-6 p-4 bg-card/60 border-primary/20 ${
								isAnalyzing ? "animate-pulse" : ""
							}`}
						>
							<div className="flex items-center justify-between mb-2">
								<div>
									<p className="text-sm font-semibold text-foreground">
										Analyzing documents
									</p>
									<p className="text-xs text-muted-foreground">
										{progressMessage}
									</p>
								</div>
								<span className="text-sm font-semibold text-foreground">
									{Math.round(analysisProgress)}%
								</span>
							</div>
							<div className="flex flex-wrap gap-3 mb-3">
								{progressStages.map((stage) => {
									const Icon = stage.icon;
									const isActive = analysisProgress >= stage.threshold;
									return (
										<div
											key={stage.label}
											className={`flex items-center gap-1 text-xs rounded-full px-2 py-1 transition-all duration-300 ${
												isActive
													? "bg-primary/10 text-primary"
													: "text-muted-foreground"
											}`}
										>
											<Icon
												className={`h-4 w-4 ${
													isActive && isAnalyzing ? "animate-bounce" : ""
												}`}
											/>
											<span>{stage.label}</span>
										</div>
									);
								})}
							</div>
							<Progress
								value={analysisProgress}
								className="transition-all duration-500 ease-out"
							/>
						</Card>
					)}

				{/* Table and Summary - Full Width Below */}
				<div className="space-y-6">
					{/* Recommendations Table */}
					<RecommendationsTable
						recommendations={recommendations}
						onFeedback={handleFeedback}
					/>

					{/* Download Button */}
					<div className="flex justify-end">
						<DownloadButton recommendations={recommendations} />
					</div>

					{/* Summary Section */}
					<SummarySection
						recommendations={recommendations}
						uprSummary={uprSummary}
						fmsiSummary={fmsiSummary}
					/>
				</div>
			</main>
		</div>
	);
};

export default Index;

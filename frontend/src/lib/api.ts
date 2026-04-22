/**
 * Frontend API client for the FMSI UN Recommendations backend.
 * Endpoints: POST /matches (un_doc, fmsi_pdf), POST /feedback.
 * Local dev: http://localhost:8000. Docker/prod: same-origin /api (nginx proxies to backend via BACKEND_URL).
 */
const API_BASE =
	import.meta.env.VITE_API_URL ??
	(import.meta.env.PROD ? "" : "http://localhost:8000");
const API_PREFIX =
	import.meta.env.PROD && !import.meta.env.VITE_API_URL ? "/api" : "";

export interface SourceData {
	theme: string;
	recommendation: string;
	beneficiaries: string;
}

export interface ReferenceData {
	theme: string;
	recommendation: string;
	domain: string;
}

export interface CategoryBreakdown {
	name: string;
	count: number;
}

export interface UprSummary {
	totalRecommendations: number;
	categories: CategoryBreakdown[];
}

export interface FmsiSummary {
	totalRecommendations: number;
	categories: CategoryBreakdown[];
}

export interface RecommendationResponse {
	id: string;
	matchId: string;
	matchEntryId: string;
	category: string;
	status: "supported" | "noted";
	source: SourceData;
	reference: ReferenceData;
	score: number;
	feedback: "correct" | "incorrect" | null;
}

export interface ProgressResponse {
	jobId: string;
	status: "pending" | "processing" | "completed" | "failed" | "unknown";
	percent: number;
	message: string;
}

export interface AnalysisSessionResponse {
	id: string;
	created_at: string;
	reference_filename: string | null;
	source_filename: string | null;
	status: "processing" | "completed" | "failed";
	recommendations: RecommendationResponse[];
	uprSummary: UprSummary;
	fmsiSummary: FmsiSummary;
}

interface BackendMatchEntry {
	match_id: string;
	score: number;
	source_index: number;
	source_text: string;
	source_row?: Record<string, unknown>;
	target_index: number;
	target_text: string;
	target_row: Record<string, unknown>;
}

interface BackendMatchResponse {
	prediction_id: string;
	matches: BackendMatchEntry[];
	upr_total_recommendations: number;
	upr_category_counts: CategoryBreakdown[];
	fmsi_total_recommendations: number;
	fmsi_category_counts: CategoryBreakdown[];
}

function mapMatchToRecommendation(
	match: BackendMatchEntry,
	predictionId: string,
): RecommendationResponse {
	const source = (match.source_row ?? {}) as Record<string, string>;
	const target = match.target_row as Record<string, string>;
	const sourceTheme =
		source.theme ?? source.Theme ?? source.category ?? source.Category ?? "";
	const sourceBeneficiaries =
		source.beneficiaries ??
		source.Beneficiaries ??
		source.groups_of_persons ??
		"";
	const sourceRecommendation =
		source.recommendation ?? source.Recommendation ?? match.source_text;
	const targetTheme = target.Theme ?? target.theme ?? "";
	const domain =
		target.Domain ??
		target.domain ??
		target["Human rights themes and groups of persons"] ??
		target["Human rights themes"] ??
		target["Human rights themes & groups of persons"] ??
		target["Relevant SDGs"] ??
		"";
	const recommendation =
		target["Recommendation and recommending State"] ??
		target.Recommendation ??
		match.target_text;
	const positionOfState =
		target["Position of the State under review"] || target.state_position || "";
	const status = positionOfState?.toLowerCase().includes("noted")
		? "noted"
		: "supported";

	return {
		id: match.match_id,
		matchId: predictionId,
		matchEntryId: match.match_id,
		category: sourceTheme || targetTheme || "—",
		status,
		source: {
			theme: sourceTheme,
			recommendation: sourceRecommendation,
			beneficiaries: sourceBeneficiaries,
		},
		reference: {
			theme: targetTheme,
			recommendation: recommendation || match.target_text,
			domain,
		},
		score: Math.round(match.score * 100),
		feedback: null,
	};
}

const DOCX_EXT = [".docx", ".doc"];

function isDocx(file: File): boolean {
	const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
	return DOCX_EXT.includes(ext);
}

function isPdf(file: File): boolean {
	return file.name.toLowerCase().endsWith(".pdf");
}

export async function analyzeDocuments(
	referenceFile: File,
	sourceFile: File,
	jobId?: string,
): Promise<AnalysisSessionResponse> {
	const docxFile = isDocx(referenceFile)
		? referenceFile
		: isDocx(sourceFile)
			? sourceFile
			: null;
	const pdfFile = isPdf(referenceFile)
		? referenceFile
		: isPdf(sourceFile)
			? sourceFile
			: null;
	if (!docxFile || !pdfFile) {
		throw new Error(
			"Expected one DOCX (.doc/.docx) and one PDF. Please upload one of each.",
		);
	}
	const formData = new FormData();
	formData.append("fmsi_pdf", pdfFile);
	formData.append("un_doc", docxFile);
	if (jobId) {
		formData.append("job_id", jobId);
	}

	const base = `${API_BASE}${API_PREFIX}`.replace(/\/$/, "");
	const res = await fetch(`${base}/matches`, {
		method: "POST",
		body: formData,
	});

	if (!res.ok) {
		const error = await res.json().catch(() => ({ detail: "Analysis failed" }));
		throw new Error((error as { detail?: string }).detail || "Analysis failed");
	}

	const data = (await res.json()) as BackendMatchResponse;
	const recommendations = data.matches.map((m) =>
		mapMatchToRecommendation(m, data.prediction_id),
	);
	return {
		id: data.prediction_id,
		created_at: new Date().toISOString(),
		reference_filename: referenceFile.name,
		source_filename: sourceFile.name,
		status: "completed",
		recommendations,
		uprSummary: {
			totalRecommendations: data.upr_total_recommendations,
			categories: data.upr_category_counts ?? [],
		},
		fmsiSummary: {
			totalRecommendations: data.fmsi_total_recommendations,
			categories: data.fmsi_category_counts ?? [],
		},
	};
}

export async function submitFeedback(
	matchId: string,
	matchEntryId: string,
	feedback: "correct" | "incorrect",
	comment?: string,
): Promise<{ id: string }> {
	const base = `${API_BASE}${API_PREFIX}`.replace(/\/$/, "");
	const res = await fetch(`${base}/feedback`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			prediction_id: matchId,
			match_id: matchEntryId,
			thumb_up: feedback === "correct",
			notes: comment ?? null,
		}),
	});

	if (!res.ok) {
		const error = await res
			.json()
			.catch(() => ({ detail: "Failed to submit feedback" }));
		throw new Error(
			(error as { detail?: string }).detail || "Failed to submit feedback",
		);
	}

	const data = (await res.json()) as { feedback_id: string };
	return { id: data.feedback_id };
}

export async function fetchProgress(jobId: string): Promise<ProgressResponse> {
	const base = `${API_BASE}${API_PREFIX}`.replace(/\/$/, "");
	const res = await fetch(`${base}/progress/${jobId}`);
	if (!res.ok) {
		throw new Error("Failed to fetch analysis progress");
	}
	const data = (await res.json()) as {
		job_id: string;
		status: ProgressResponse["status"];
		percent: number;
		message: string;
	};
	return {
		jobId: data.job_id,
		status: data.status,
		percent: data.percent,
		message: data.message,
	};
}

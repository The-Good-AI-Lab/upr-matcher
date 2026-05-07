import {
	AlertTriangle,
	CheckCircle2,
	ChevronDown,
	Clock,
	History,
	Loader2,
	Trash2,
	XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { deleteJob, fetchUserJobs, type JobSummary } from "@/lib/api";

interface PreviousRunsProps {
	onLoadRun: (job: JobSummary) => void;
}

const STALE_MINUTES = 10;

function parseDbTimestamp(ts: string): Date {
	// SQLite CURRENT_TIMESTAMP is UTC but has no 'Z' suffix — add it so JS
	// doesn't interpret it as local time.
	const normalised =
		ts.includes("T") || ts.endsWith("Z") ? ts : `${ts.replace(" ", "T")}Z`;
	return new Date(normalised);
}

function isStale(job: JobSummary): boolean {
	if (job.status !== "pending" && job.status !== "processing") return false;
	const ts = job.updatedAt ?? job.createdAt;
	if (!ts) return false;
	return (Date.now() - parseDbTimestamp(ts).getTime()) / 60_000 > STALE_MINUTES;
}

function formatDate(iso: string | null): string {
	if (!iso) return "—";
	return parseDbTimestamp(iso).toLocaleString(undefined, {
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

function stripUploadPrefix(filename: string | null): string {
	if (!filename) return "—";
	const match = filename.match(/^[0-9a-f-]{36}_(.+)$/i);
	return match ? match[1] : filename;
}

function StatusIcon({ job }: { job: JobSummary }) {
	if (isStale(job))
		return <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-500" />;
	switch (job.status) {
		case "completed":
			return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-500" />;
		case "failed":
			return <XCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />;
		case "processing":
			return (
				<Loader2 className="h-3.5 w-3.5 shrink-0 text-blue-500 animate-spin" />
			);
		default:
			return <Clock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />;
	}
}

export function PreviousRuns({ onLoadRun }: PreviousRunsProps) {
	const [jobs, setJobs] = useState<JobSummary[]>([]);
	const [loading, setLoading] = useState(false);
	const [open, setOpen] = useState(false);
	const [busy, setBusy] = useState<string | null>(null);

	useEffect(() => {
		if (!open) return;
		setLoading(true);
		fetchUserJobs()
			.then(setJobs)
			.catch(() => setJobs([]))
			.finally(() => setLoading(false));
	}, [open]);

	const handleDelete = async (job: JobSummary) => {
		setBusy(job.jobId);
		try {
			await deleteJob(job.jobId);
			setJobs((prev) => prev.filter((j) => j.jobId !== job.jobId));
		} catch {
			fetchUserJobs()
				.then(setJobs)
				.catch(() => {});
		} finally {
			setBusy(null);
		}
	};

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button variant="outline" size="sm" className="gap-1.5">
					<History className="h-4 w-4" />
					Previous runs
					<ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
				</Button>
			</PopoverTrigger>
			<PopoverContent align="end" className="w-96 p-0">
				<p className="px-4 py-3 text-sm font-semibold">Your previous runs</p>
				<Separator />
				{loading ? (
					<div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
						<Loader2 className="h-4 w-4 animate-spin" />
						<span className="text-sm">Loading…</span>
					</div>
				) : jobs.length === 0 ? (
					<p className="py-8 text-center text-sm text-muted-foreground">
						No previous runs found.
					</p>
				) : (
					<div className="overflow-y-auto max-h-[360px] p-1">
						{jobs.map((job) => {
							const stale = isStale(job);
							const isBusy = busy === job.jobId;
							return (
								<div
									key={job.jobId}
									className={`flex items-center gap-2 rounded-sm px-2 py-1.5 ${stale ? "bg-amber-50/50 dark:bg-amber-950/20" : ""}`}
								>
									<StatusIcon job={job} />

									<button
										type="button"
										disabled={job.status !== "completed"}
										onClick={() => {
											setOpen(false);
											onLoadRun(job);
										}}
										className="flex min-w-0 flex-1 flex-col text-left hover:underline disabled:cursor-not-allowed disabled:opacity-50"
									>
										<span className="truncate text-xs font-medium">
											{stripUploadPrefix(job.sourceFilename)}
										</span>
										<span className="truncate text-[11px] text-muted-foreground">
											{stripUploadPrefix(job.referenceFilename)} ·{" "}
											{formatDate(job.createdAt)}
										</span>
										{stale && (
											<span className="text-[11px] text-amber-600 dark:text-amber-400">
												No updates for {STALE_MINUTES}+ min
											</span>
										)}
									</button>

									<Badge
										variant={
											job.status === "completed"
												? "default"
												: job.status === "failed"
													? "destructive"
													: stale
														? "outline"
														: "secondary"
										}
										className={`shrink-0 px-1.5 py-0 text-[10px] ${stale ? "border-amber-400 text-amber-600" : ""}`}
									>
										{stale ? "stuck?" : job.status}
									</Badge>

									<Button
										variant="ghost"
										size="icon"
										className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive"
										disabled={isBusy}
										onClick={() => handleDelete(job)}
										title="Delete"
									>
										{isBusy ? (
											<Loader2 className="h-3.5 w-3.5 animate-spin" />
										) : (
											<Trash2 className="h-3.5 w-3.5" />
										)}
									</Button>
								</div>
							);
						})}
					</div>
				)}
			</PopoverContent>
		</Popover>
	);
}

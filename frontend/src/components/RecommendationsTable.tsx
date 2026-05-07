import {
	ChevronsLeft,
	ChevronsRight,
	ThumbsDown,
	ThumbsUp,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
	Pagination,
	PaginationContent,
	PaginationItem,
} from "@/components/ui/pagination";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

const PAGE_SIZE_OPTIONS = [5, 10, 25, 50];
const DOTS = "…" as const;

function range(start: number, end: number) {
	return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

/**
 * Standard pagination range algorithm (MUI / Mayank Gupta variant).
 *
 * With siblingCount=1 it always returns:
 *   - 1..N items  when totalPages <= 7
 *   - exactly 7 items when totalPages > 7
 *
 * The count depends only on totalPages — never on currentPage —
 * so the widget width is stable while navigating.
 */
function getPaginationRange(
	currentPage: number,
	totalPages: number,
	siblingCount = 1,
): (number | typeof DOTS)[] {
	const totalSlots = siblingCount * 2 + 5;

	if (totalSlots >= totalPages) {
		return range(1, totalPages);
	}

	const leftIdx = Math.max(currentPage - siblingCount, 1);
	const rightIdx = Math.min(currentPage + siblingCount, totalPages);
	const showLeftDots = leftIdx > 2;
	const showRightDots = rightIdx < totalPages - 2;

	if (!showLeftDots && showRightDots) {
		const left = range(1, 3 + 2 * siblingCount);
		return [...left, DOTS, totalPages];
	}

	if (showLeftDots && !showRightDots) {
		const right = range(totalPages - (3 + 2 * siblingCount) + 1, totalPages);
		return [1, DOTS, ...right];
	}

	return [1, DOTS, ...range(leftIdx, rightIdx), DOTS, totalPages];
}

export interface Recommendation {
	id: string;
	matchId: string;
	matchEntryId: string;
	category: string;
	status?: "supported" | "noted";
	source: {
		theme: string;
		recommendation: string;
		beneficiaries: string;
	};
	reference: {
		theme: string;
		recommendation: string;
		domain: string;
	};
	score: number;
	feedback?: "correct" | "incorrect" | null;
}

interface RecommendationsTableProps {
	recommendations: Recommendation[];
	onFeedback: (
		matchId: string,
		matchEntryId: string,
		feedback: "correct" | "incorrect",
	) => void;
}

export const RecommendationsTable = ({
	recommendations,
	onFeedback,
}: RecommendationsTableProps) => {
	const [page, setPage] = useState(1);
	const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0]);
	const [pageInput, setPageInput] = useState("1");

	const sorted = useMemo(
		() => [...recommendations].sort((a, b) => b.score - a.score),
		[recommendations],
	);

	const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
	const currentPage = sorted.length === 0 ? 0 : Math.min(page, totalPages);
	const offset = currentPage === 0 ? 0 : (currentPage - 1) * pageSize;
	const pageRows = sorted.slice(offset, offset + pageSize);
	const showingFrom = sorted.length === 0 ? 0 : offset + 1;
	const showingTo = Math.min(sorted.length, offset + pageRows.length);
	const disabled = sorted.length === 0;

	const paginationRange = useMemo(
		() =>
			currentPage === 0 ? [] : getPaginationRange(currentPage, totalPages),
		[currentPage, totalPages],
	);

	useEffect(() => {
		setPage((p) => Math.min(Math.max(p, 1), totalPages));
	}, [totalPages]);

	useEffect(() => {
		setPageInput(currentPage === 0 ? "" : String(currentPage));
	}, [currentPage]);

	const goTo = (n: number) => setPage(Math.min(Math.max(n, 1), totalPages));

	const handlePageSizeChange = (value: string) => {
		const next = Number(value);
		setPageSize(next);
		setPage(Math.max(Math.ceil((offset + 1) / next), 1));
	};

	const handleJump = (e: FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		const n = Number(pageInput);
		if (Number.isFinite(n) && n > 0) goTo(n);
		else setPageInput(currentPage === 0 ? "" : String(currentPage));
	};

	const getScoreBadgeVariant = (score: number) => {
		if (score >= 80) return "default";
		if (score >= 60) return "secondary";
		return "outline";
	};

	return (
		<Card>
			<div className="p-4 border-b bg-muted/50 space-y-3">
				<div className="flex flex-wrap items-center justify-between gap-2">
					<h3 className="font-semibold text-foreground">
						Recommendation Matches
					</h3>
					<p className="text-sm text-muted-foreground">
						Showing {showingFrom}–{showingTo} of {sorted.length} matches
					</p>
				</div>

				<div className="flex flex-wrap items-center justify-between gap-3">
					<div className="flex items-center gap-2 text-sm text-muted-foreground">
						<span>Rows per page</span>
						<Select
							value={String(pageSize)}
							onValueChange={handlePageSizeChange}
							disabled={disabled}
						>
							<SelectTrigger
								className="h-8 w-[72px]"
								aria-label="Rows per page"
							>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{PAGE_SIZE_OPTIONS.map((opt) => (
									<SelectItem key={opt} value={String(opt)}>
										{opt}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>

					<div className="flex items-center gap-2">
						<Pagination className="mx-0 w-auto">
							<PaginationContent>
								<PaginationItem>
									<Button
										variant="outline"
										size="icon"
										onClick={() => goTo(1)}
										disabled={disabled || currentPage === 1}
										aria-label="First page"
									>
										<ChevronsLeft className="h-4 w-4" />
									</Button>
								</PaginationItem>

								{paginationRange.map((item, i) => (
									<PaginationItem
										// biome-ignore lint/suspicious/noArrayIndexKey: positional pagination slots
										key={i}
									>
										{item === DOTS ? (
											<span className="flex h-9 w-9 items-center justify-center text-sm text-muted-foreground select-none">
												{DOTS}
											</span>
										) : (
											<Button
												variant={item === currentPage ? "default" : "ghost"}
												size="icon"
												className="w-9"
												onClick={() => goTo(item)}
												aria-current={item === currentPage ? "page" : undefined}
												aria-label={`Page ${item}`}
											>
												{item}
											</Button>
										)}
									</PaginationItem>
								))}

								<PaginationItem>
									<Button
										variant="outline"
										size="icon"
										onClick={() => goTo(totalPages)}
										disabled={disabled || currentPage === totalPages}
										aria-label="Last page"
									>
										<ChevronsRight className="h-4 w-4" />
									</Button>
								</PaginationItem>
							</PaginationContent>
						</Pagination>

						<form
							className="flex items-center gap-1.5 text-sm text-muted-foreground"
							onSubmit={handleJump}
						>
							<label htmlFor="page-jump" className="whitespace-nowrap">
								Go to
							</label>
							<Input
								id="page-jump"
								type="number"
								min={1}
								max={totalPages}
								value={pageInput}
								onChange={(e) => setPageInput(e.target.value)}
								disabled={disabled}
								className="h-8 w-14 text-center"
							/>
							<Button
								type="submit"
								variant="outline"
								size="sm"
								disabled={disabled}
							>
								Go
							</Button>
						</form>
					</div>
				</div>
			</div>

			<div className="overflow-x-auto">
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead
								colSpan={3}
								className="text-center border-r bg-muted/30"
							>
								Source Recommendation
							</TableHead>
							<TableHead
								colSpan={4}
								className="text-center border-r bg-muted/30"
							>
								Reference Recommendation
							</TableHead>
							<TableHead
								rowSpan={2}
								className="text-center align-middle bg-muted/30"
							>
								Score
							</TableHead>
							<TableHead
								rowSpan={2}
								className="text-center align-middle bg-muted/30"
							>
								Feedback
							</TableHead>
						</TableRow>
						<TableRow>
							<TableHead className="w-[15%]">Theme</TableHead>
							<TableHead className="w-[20%]">Recommendation</TableHead>
							<TableHead className="w-[10%] border-r">Beneficiaries</TableHead>
							<TableHead className="w-[15%]">Theme</TableHead>
							<TableHead className="w-[20%]">Recommendation</TableHead>
							<TableHead className="w-[18%] border-r">
								Themes &amp; Beneficiaries
							</TableHead>
							<TableHead className="w-[7%] border-r text-center">
								Status
							</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{pageRows.length > 0 ? (
							pageRows.map((rec) => (
								<TableRow
									key={rec.id}
									className={
										rec.feedback === "correct"
											? "bg-success/10"
											: rec.feedback === "incorrect"
												? "bg-destructive/10"
												: "bg-accent/10"
									}
								>
									<TableCell className="text-sm">{rec.source.theme}</TableCell>
									<TableCell className="text-sm">
										{rec.source.recommendation}
									</TableCell>
									<TableCell className="text-sm border-r">
										{rec.source.beneficiaries}
									</TableCell>
									<TableCell className="text-sm">
										{rec.reference.theme}
									</TableCell>
									<TableCell className="text-sm">
										{rec.reference.recommendation}
									</TableCell>
									<TableCell className="text-sm border-r">
										{rec.reference.domain}
									</TableCell>
									<TableCell className="text-center text-sm font-semibold border-r w-[7%]">
										{rec.status ? (
											<span
												className={
													rec.status === "supported"
														? "text-emerald-600"
														: "text-muted-foreground"
												}
											>
												{rec.status.toUpperCase()}
											</span>
										) : (
											"—"
										)}
									</TableCell>
									<TableCell className="text-center">
										<Badge variant={getScoreBadgeVariant(rec.score)}>
											{rec.score}%
										</Badge>
									</TableCell>
									<TableCell className="text-center">
										<div className="flex gap-2 justify-center">
											<Button
												variant={
													rec.feedback === "correct" ? "default" : "outline"
												}
												size="sm"
												onClick={() =>
													onFeedback(rec.matchId, rec.matchEntryId, "correct")
												}
												className={
													rec.feedback === "correct"
														? "bg-success hover:bg-success/90"
														: ""
												}
											>
												<ThumbsUp className="h-4 w-4" />
											</Button>
											<Button
												variant={
													rec.feedback === "incorrect" ? "default" : "outline"
												}
												size="sm"
												onClick={() =>
													onFeedback(rec.matchId, rec.matchEntryId, "incorrect")
												}
												className={
													rec.feedback === "incorrect"
														? "bg-destructive hover:bg-destructive/90"
														: ""
												}
											>
												<ThumbsDown className="h-4 w-4" />
											</Button>
										</div>
									</TableCell>
								</TableRow>
							))
						) : (
							<TableRow>
								<TableCell
									colSpan={9}
									className="text-center py-8 text-muted-foreground"
								>
									No recommendations available yet.
								</TableCell>
							</TableRow>
						)}
					</TableBody>
				</Table>
			</div>
		</Card>
	);
};

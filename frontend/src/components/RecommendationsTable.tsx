import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

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
	const [page, setPage] = useState(0);
	const PAGE_SIZE = 5;

	const getScoreBadgeVariant = (score: number) => {
		if (score >= 80) return "default";
		if (score >= 60) return "secondary";
		return "outline";
	};

	const sortedRecommendations = [...recommendations].sort(
		(a, b) => b.score - a.score,
	);
	const filteredRecommendations = sortedRecommendations;
	const totalPages = Math.max(
		1,
		Math.ceil(filteredRecommendations.length / PAGE_SIZE),
	);
	const currentPage = Math.min(page, totalPages - 1);
	const pageStartIndex = currentPage * PAGE_SIZE;
	const pageRecommendations = filteredRecommendations.slice(
		pageStartIndex,
		pageStartIndex + PAGE_SIZE,
	);
	const pageStartCount =
		filteredRecommendations.length === 0 ? 0 : pageStartIndex + 1;
	const pageEndCount = Math.min(
		filteredRecommendations.length,
		pageStartIndex + pageRecommendations.length,
	);

	return (
		<Card>
			<div className="p-4 border-b bg-muted/50">
				<div className="flex items-center justify-between">
					<h3 className="font-semibold text-foreground">
						Recommendation Matches
					</h3>
					<p className="text-sm text-muted-foreground">
						Showing {pageStartCount}-{pageEndCount} of{" "}
						{filteredRecommendations.length} matches
					</p>
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
						{pageRecommendations.length > 0 ? (
							pageRecommendations.map((rec) => (
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
			<div className="flex items-center justify-between px-4 py-3 border-t bg-muted/40 text-sm">
				<span>
					Page {filteredRecommendations.length === 0 ? 0 : currentPage + 1} of{" "}
					{filteredRecommendations.length === 0 ? 0 : totalPages}
				</span>
				<div className="space-x-2">
					<Button
						variant="outline"
						size="sm"
						onClick={() => setPage((prev) => Math.max(prev - 1, 0))}
						disabled={currentPage === 0 || filteredRecommendations.length === 0}
					>
						Previous
					</Button>
					<Button
						variant="outline"
						size="sm"
						onClick={() =>
							setPage((prev) => Math.min(prev + 1, totalPages - 1))
						}
						disabled={
							filteredRecommendations.length === 0 ||
							currentPage >= totalPages - 1
						}
					>
						Next
					</Button>
				</div>
			</div>
		</Card>
	);
};

import { Tag, ThumbsDown, ThumbsUp, TrendingUp } from "lucide-react";
import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import type { FmsiSummary, UprSummary } from "@/lib/api";
import type { Recommendation } from "./RecommendationsTable";

type SummarySectionProps = {
	recommendations: Recommendation[];
	uprSummary?: UprSummary | null;
	fmsiSummary?: FmsiSummary | null;
};

const CATEGORY_COLORS = [
	"text-primary",
	"text-accent",
	"text-purple-500",
	"text-green-500",
	"text-orange-500",
	"text-blue-500",
	"text-pink-500",
	"text-teal-500",
];

const getCategoryColor = (index: number) =>
	CATEGORY_COLORS[index % CATEGORY_COLORS.length];

export const SummarySection = ({
	recommendations,
	uprSummary,
	fmsiSummary,
}: SummarySectionProps) => {
	const totalMatches = recommendations.length;
	const averageScore =
		totalMatches > 0
			? Math.round(
					recommendations.reduce((sum, r) => sum + r.score, 0) / totalMatches,
				)
			: 0;

	const distinctSourceRecommendations = useMemo(() => {
		const seen = new Map<string, Recommendation>();
		recommendations.forEach((rec) => {
			const key =
				rec.source.recommendation?.trim() ||
				rec.id ||
				`${rec.matchId}-${rec.matchEntryId}`;
			if (!seen.has(key)) {
				seen.set(key, rec);
			}
		});
		return Array.from(seen.values());
	}, [recommendations]);

	const distinctReferenceRecommendations = useMemo(() => {
		const seen = new Map<string, Recommendation>();
		recommendations.forEach((rec) => {
			const key =
				rec.reference.recommendation?.trim() ||
				`ref-${rec.matchId}-${rec.matchEntryId}`;
			if (!seen.has(key)) {
				seen.set(key, rec);
			}
		});
		return Array.from(seen.values());
	}, [recommendations]);

	const totalDistinctSourceRecommendations =
		distinctSourceRecommendations.length;

	const fallbackFmsiCategoryData = useMemo(() => {
		const counts = new Map<string, number>();
		distinctSourceRecommendations.forEach((rec) => {
			const categoryName = rec.source.theme || rec.category || "Uncategorized";
			counts.set(categoryName, (counts.get(categoryName) ?? 0) + 1);
		});

		return Array.from(counts.entries()).map(([name, count]) => ({
			name,
			count,
		}));
	}, [distinctSourceRecommendations]);
	const totalFmsiRecommendations =
		fmsiSummary?.totalRecommendations ?? totalDistinctSourceRecommendations;

	const fmsiSummaryCategories = useMemo(() => {
		const baseCategories =
			fmsiSummary?.categories && fmsiSummary.categories.length > 0
				? fmsiSummary.categories
				: fallbackFmsiCategoryData;

		return baseCategories
			.map((category) => ({ name: category.name, count: category.count }))
			.sort((a, b) => b.count - a.count)
			.map((category, index) => ({
				...category,
				color: getCategoryColor(index),
			}));
	}, [fmsiSummary, fallbackFmsiCategoryData]);

	const fallbackUprCategoryData = useMemo(() => {
		const counts = new Map<string, number>();
		distinctReferenceRecommendations.forEach((rec) => {
			const categoryName = rec.reference.theme || "Uncategorized";
			counts.set(categoryName, (counts.get(categoryName) ?? 0) + 1);
		});

		return Array.from(counts.entries()).map(([name, count]) => ({
			name,
			count,
		}));
	}, [distinctReferenceRecommendations]);

	const totalUprRecommendations =
		uprSummary?.totalRecommendations ?? distinctReferenceRecommendations.length;

	const uprSummaryCategories = useMemo(() => {
		const baseCategories =
			uprSummary?.categories && uprSummary.categories.length > 0
				? uprSummary.categories
				: fallbackUprCategoryData;

		return baseCategories
			.map((category) => ({ name: category.name, count: category.count }))
			.sort((a, b) => b.count - a.count)
			.map((category, index) => ({
				...category,
				color: getCategoryColor(index + 4),
			}));
	}, [uprSummary, fallbackUprCategoryData]);

	const totalFmsiThemes = fmsiSummaryCategories.length;
	const totalUprThemes = uprSummaryCategories.length;

	const fmsiMatchCategories = useMemo(() => {
		const counts = new Map<string, number>();
		recommendations.forEach((rec) => {
			const name =
				rec.source.theme?.trim() || rec.category?.trim() || "Uncategorized";
			counts.set(name, (counts.get(name) ?? 0) + 1);
		});

		return Array.from(counts.entries())
			.sort((a, b) => b[1] - a[1])
			.map(([name, count], index) => ({
				name,
				count,
				color: getCategoryColor(index),
			}));
	}, [recommendations]);

	const uprMatchCategories = useMemo(() => {
		const counts = new Map<string, number>();
		recommendations.forEach((rec) => {
			const name =
				rec.reference.theme?.trim() ||
				rec.reference.domain?.trim() ||
				"Uncategorized";
			counts.set(name, (counts.get(name) ?? 0) + 1);
		});

		return Array.from(counts.entries())
			.sort((a, b) => b[1] - a[1])
			.map(([name, count], index) => ({
				name,
				count,
				color: getCategoryColor(index + 4),
			}));
	}, [recommendations]);

	const { supportedMatches, notedMatches } = useMemo(() => {
		return recommendations.reduce(
			(acc, rec) => {
				if (rec.status === "supported") {
					acc.supportedMatches += 1;
				} else if (rec.status === "noted") {
					acc.notedMatches += 1;
				}
				return acc;
			},
			{ supportedMatches: 0, notedMatches: 0 },
		);
	}, [recommendations]);

	const renderCategoryList = (
		categories: { name: string; count: number; color: string }[],
		emptyLabel: string,
		totalCount: number,
	) => {
		if (categories.length === 0 || totalCount === 0) {
			return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
		}
		return categories.map((category) => (
			<div
				key={category.name}
				className="p-4 rounded-lg bg-muted/30 border border-border"
			>
				<div className="flex items-start gap-3 mb-3">
					<Tag className={`h-5 w-5 mt-0.5 ${category.color}`} />
					<div className="flex-1">
						<h5 className="font-semibold text-sm text-foreground mb-1">
							{category.name}
						</h5>
						<p className="text-xs text-muted-foreground">
							{((category.count / totalCount) * 100).toFixed(1)}% of matches
						</p>
					</div>
				</div>
				<div className="w-full bg-muted rounded-full h-2">
					<div
						className={`h-2 rounded-full transition-all ${
							category.count >= 5
								? "bg-primary"
								: category.count >= 3
									? "bg-accent"
									: "bg-muted-foreground"
						}`}
						style={{
							width: `${
								totalCount > 0
									? Math.max((category.count / totalCount) * 100, 6)
									: 0
							}%`,
						}}
					/>
				</div>
			</div>
		));
	};

	return (
		<Card className="p-6">
			<h3 className="text-lg font-semibold mb-6 text-foreground">
				Analysis Summary
			</h3>

			<div className="mb-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
				<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
					<div className="p-2 rounded-full bg-primary/10">
						<TrendingUp className="h-5 w-5 text-primary" />
					</div>
					<div>
						<p className="text-xs text-muted-foreground">Average Score</p>
						<p className="text-2xl font-bold text-foreground">
							{averageScore}%
						</p>
					</div>
				</div>

				<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
					<div className="p-2 rounded-full bg-accent/10">
						<TrendingUp className="h-5 w-5 text-accent" />
					</div>
					<div>
						<p className="text-xs text-muted-foreground">Total Matches</p>
						<p className="text-2xl font-bold text-foreground">{totalMatches}</p>
					</div>
				</div>

				<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
					<div className="p-2 rounded-full bg-emerald-100">
						<ThumbsUp className="h-5 w-5 text-emerald-600" />
					</div>
					<div>
						<p className="text-xs text-muted-foreground">Supported Matches</p>
						<p className="text-2xl font-bold text-foreground">
							{supportedMatches}
						</p>
					</div>
				</div>

				<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
					<div className="p-2 rounded-full bg-slate-200">
						<ThumbsDown className="h-5 w-5 text-slate-600" />
					</div>
					<div>
						<p className="text-xs text-muted-foreground">Noted Matches</p>
						<p className="text-2xl font-bold text-foreground">{notedMatches}</p>
					</div>
				</div>
			</div>

			<p className="text-xs text-muted-foreground mb-4">
				Note: The summaries below include every recommendation extracted from
				the uploaded documents, not only the matches listed above.
			</p>

			<div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
				<div className="space-y-6">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
							<div className="p-2 rounded-full bg-purple-100">
								<Tag className="h-5 w-5 text-purple-600" />
							</div>
							<div>
								<p className="text-xs text-muted-foreground">
									Source Document Recommendations
								</p>
								<p className="text-2xl font-bold text-foreground">
									{totalFmsiRecommendations}
								</p>
							</div>
						</div>

						<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
							<div className="p-2 rounded-full bg-green-100">
								<Tag className="h-5 w-5 text-green-600" />
							</div>
							<div>
								<p className="text-xs text-muted-foreground">
									Source Document Themes
								</p>
								<p className="text-2xl font-bold text-foreground">
									{totalFmsiThemes}
								</p>
							</div>
						</div>
					</div>
					<div className="space-y-4">
						<h4 className="text-sm font-semibold text-foreground">
							Source Document Theme Breakdown
						</h4>
						{renderCategoryList(
							fmsiMatchCategories,
							"No source document matches to analyze",
							totalMatches,
						)}
					</div>
				</div>

				<div className="space-y-6">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
							<div className="p-2 rounded-full bg-primary/10">
								<Tag className="h-5 w-5 text-primary" />
							</div>
							<div>
								<p className="text-xs text-muted-foreground">
									UPR Recommendations
								</p>
								<p className="text-2xl font-bold text-foreground">
									{totalUprRecommendations}
								</p>
							</div>
						</div>

						<div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
							<div className="p-2 rounded-full bg-accent/10">
								<Tag className="h-5 w-5 text-accent" />
							</div>
							<div>
								<p className="text-xs text-muted-foreground">UPR Themes</p>
								<p className="text-2xl font-bold text-foreground">
									{totalUprThemes}
								</p>
							</div>
						</div>
					</div>
					<div className="space-y-4">
						<h4 className="text-sm font-semibold text-foreground">
							UPR Theme Breakdown
						</h4>
						{renderCategoryList(
							uprMatchCategories,
							"No UPR matches to analyze",
							totalMatches,
						)}
					</div>
				</div>
			</div>
		</Card>
	);
};

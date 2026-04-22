import { Download } from "lucide-react";
import { toast } from "sonner";
import * as XLSX from "xlsx";
import { Button } from "@/components/ui/button";
import type { Recommendation } from "./RecommendationsTable";

interface DownloadButtonProps {
	recommendations: Recommendation[];
}

export const DownloadButton = ({ recommendations }: DownloadButtonProps) => {
	const handleDownload = () => {
		try {
			if (recommendations.length === 0) {
				toast.error("No recommendations to download");
				return;
			}

			const workbook = XLSX.utils.book_new();
			const usedSheetNames = new Set<string>();
			const summaryRows: {
				"Sheet Name": string;
				Theme: string;
				Matches: number;
			}[] = [];

			const themeGroups = recommendations.reduce((acc, rec) => {
				const key = rec.source.theme?.trim() || "Uncategorized";
				let list = acc.get(key);
				if (!list) {
					list = [];
					acc.set(key, list);
				}
				list.push(rec);
				return acc;
			}, new Map<string, Recommendation[]>());

			const invalidSheetChars = new Set([":", "\\", "/", "?", "*", "[", "]"]);
			const makeSheetName = (rawName: string) => {
				const sanitized =
					Array.from(rawName)
						.map((char) => (invalidSheetChars.has(char) ? "_" : char))
						.join("")
						.trim() || "Theme";
				const base =
					sanitized.length > 31 ? sanitized.substring(0, 31) : sanitized;
				let candidate = base;
				let counter = 1;
				while (usedSheetNames.has(candidate)) {
					const suffix = `_${counter++}`;
					const prefix = base.substring(0, Math.max(0, 31 - suffix.length));
					candidate = `${prefix}${suffix}`;
				}
				usedSheetNames.add(candidate);
				return candidate;
			};

			for (const [theme, themeRecs] of themeGroups.entries()) {
				const groupedBySourceRec = themeRecs.reduce((acc, rec) => {
					const key = rec.source.recommendation || `Recommendation ${rec.id}`;
					let list = acc.get(key);
					if (!list) {
						list = [];
						acc.set(key, list);
					}
					list.push(rec);
					return acc;
				}, new Map<string, Recommendation[]>());

				const sheetRows: Record<string, string | number>[] = [];
				for (const [sourceRec, matches] of groupedBySourceRec.entries()) {
					matches.forEach((match, index) => {
						sheetRows.push({
							"Source Document Recommendation": index === 0 ? sourceRec : "",
							"Source Document Beneficiaries":
								index === 0 ? match.source.beneficiaries : "",
							"UPR Theme": match.reference.theme,
							"UPR Recommendation": match.reference.recommendation,
							Status: match.status ? match.status.toUpperCase() : "",
							"UPR Themes & Beneficiaries": match.reference.domain,
							"Score (%)": match.score,
						});
					});
					sheetRows.push({});
				}
				if (
					sheetRows[sheetRows.length - 1] &&
					Object.keys(sheetRows[sheetRows.length - 1]).length === 0
				) {
					sheetRows.pop();
				}

				const worksheet = XLSX.utils.json_to_sheet(sheetRows);
				worksheet["!cols"] = [
					{ wch: 50 }, // Source Document Recommendation
					{ wch: 25 }, // Source Document Beneficiaries
					{ wch: 20 }, // UPR Theme
					{ wch: 50 }, // UPR Recommendation
					{ wch: 10 }, // Status
					{ wch: 25 }, // UPR Themes & Beneficiaries
					{ wch: 10 }, // Score
				];

				const sheetName = makeSheetName(theme);
				XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
				summaryRows.push({
					"Sheet Name": sheetName,
					Theme: theme,
					Matches: themeRecs.length,
				});
			}

			if (summaryRows.length > 0) {
				const summarySheet = XLSX.utils.json_to_sheet(summaryRows);
				summarySheet["!cols"] = [{ wch: 25 }, { wch: 50 }, { wch: 12 }];
				XLSX.utils.book_append_sheet(workbook, summarySheet, "Summary");
			}

			const timestamp = new Date().toISOString().split("T")[0];
			const filename = `UPR_Matcher_Results_${timestamp}.xlsx`;

			XLSX.writeFile(workbook, filename);

			toast.success(`Downloaded ${recommendations.length} recommendations`);
		} catch (error) {
			console.error("Download error:", error);
			toast.error("Failed to download file");
		}
	};

	return (
		<Button
			onClick={handleDownload}
			variant="default"
			className="w-full md:w-auto"
			disabled={recommendations.length === 0}
		>
			<Download className="h-4 w-4 mr-2" />
			Download Results ({recommendations.length} matches)
		</Button>
	);
};

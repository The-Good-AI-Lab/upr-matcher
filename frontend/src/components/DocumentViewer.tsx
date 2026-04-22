import { renderAsync } from "docx-preview";
import { FileText, Minimize2, Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";
import "@/styles/docx-preview.css";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

interface DocumentViewerProps {
	fileName: string;
	content: string;
	isHtml?: boolean;
	isDocx?: boolean;
	docxArrayBuffer?: ArrayBuffer;
	onMinimize?: () => void;
	onDelete?: () => void;
}

export const DocumentViewer = ({
	fileName,
	content,
	isHtml = false,
	isDocx = false,
	docxArrayBuffer,
	onMinimize,
	onDelete,
}: DocumentViewerProps) => {
	const docxContainerRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		if (!isDocx || !docxArrayBuffer || !docxContainerRef.current) {
			return;
		}

		const container = docxContainerRef.current;
		container.innerHTML = "";

		renderAsync(docxArrayBuffer, container).catch((error) => {
			console.error("Failed to render DOCX preview", error);
		});

		return () => {
			if (container) {
				container.innerHTML = "";
			}
		};
	}, [isDocx, docxArrayBuffer]);

	return (
		<Card className="h-full">
			<div className="p-4 border-b bg-muted/50">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						<FileText className="h-5 w-5 text-primary" />
						<h3 className="font-semibold text-foreground">{fileName}</h3>
					</div>
					<div className="flex gap-2">
						{onMinimize && (
							<Button
								variant="ghost"
								size="sm"
								onClick={onMinimize}
								className="h-8"
							>
								<Minimize2 className="h-4 w-4 mr-2" />
								Minimize
							</Button>
						)}
						{onDelete && (
							<Button
								variant="ghost"
								size="sm"
								onClick={onDelete}
								className="h-8 text-destructive hover:text-destructive"
							>
								<Trash2 className="h-4 w-4 mr-2" />
								Delete
							</Button>
						)}
					</div>
				</div>
			</div>
			<ScrollArea className="h-[400px]">
				<div className="p-6">
					{isDocx && docxArrayBuffer ? (
						<div ref={docxContainerRef} className="docx-preview space-y-4" />
					) : isHtml ? (
						<div
							className="prose prose-sm max-w-none text-foreground"
							// biome-ignore lint/security/noDangerouslySetInnerHtml: rendered from converted docx (mammoth), not user input
							dangerouslySetInnerHTML={{ __html: content }}
						/>
					) : (
						<p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
							{content}
						</p>
					)}
				</div>
			</ScrollArea>
		</Card>
	);
};

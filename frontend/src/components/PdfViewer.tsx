import { FileText, Minimize2, Trash2 } from "lucide-react";
import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

// Set up the worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
	fileName: string;
	fileUrl: string;
	onMinimize?: () => void;
	onDelete?: () => void;
}

export const PdfViewer = ({
	fileName,
	fileUrl,
	onMinimize,
	onDelete,
}: PdfViewerProps) => {
	const [numPages, setNumPages] = useState<number>(0);

	function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
		setNumPages(numPages);
	}

	return (
		<Card className="h-full">
			<div className="p-4 border-b bg-muted/50">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						<FileText className="h-5 w-5 text-primary" />
						<h3 className="font-semibold text-foreground">{fileName}</h3>
					</div>
					<div className="flex items-center gap-2">
						{numPages > 0 && (
							<span className="text-sm text-muted-foreground">
								{numPages} page{numPages === 1 ? "" : "s"}
							</span>
						)}
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
			<ScrollArea className="h-[600px]">
				<div className="p-6 flex justify-center bg-muted/20">
					<Document
						file={fileUrl}
						onLoadSuccess={onDocumentLoadSuccess}
						loading={
							<div className="p-8 text-center text-muted-foreground">
								Loading PDF...
							</div>
						}
						error={
							<div className="p-8 text-center text-destructive">
								Failed to load PDF. Please try again.
							</div>
						}
					>
						{Array.from({ length: numPages }, (_, index) => (
							<Page
								key={`page_${index + 1}`}
								pageNumber={index + 1}
								renderTextLayer
								renderAnnotationLayer
								className="shadow-lg mb-6"
							/>
						))}
					</Document>
				</div>
			</ScrollArea>
		</Card>
	);
};

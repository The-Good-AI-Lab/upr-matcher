import { FileText, Trash2, Upload } from "lucide-react";
import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface DocumentUploadProps {
	onFileUpload: (file: File) => void;
	hasMinimizedFile?: boolean;
	minimizedFileName?: string;
	onRestoreFile?: () => void;
	onDeleteFile?: () => void;
	description?: string;
	accept?: string;
}

export const DocumentUpload = ({
	onFileUpload,
	hasMinimizedFile,
	minimizedFileName,
	onRestoreFile,
	onDeleteFile,
	description,
	accept,
}: DocumentUploadProps) => {
	const descriptionText = description ?? "Supports PDF, DOC, DOCX, TXT files";
	const acceptTypes = accept ?? ".pdf,.doc,.docx,.txt";

	const handleDrop = useCallback(
		(e: React.DragEvent<HTMLDivElement>) => {
			e.preventDefault();
			const files = Array.from(e.dataTransfer.files);
			if (files.length > 0) {
				onFileUpload(files[0]);
			}
		},
		[onFileUpload],
	);

	const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
		e.preventDefault();
	}, []);

	const handleFileInput = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			const files = e.target.files;
			if (files && files.length > 0) {
				onFileUpload(files[0]);
			}
		},
		[onFileUpload],
	);

	return (
		<div className="space-y-4">
			{hasMinimizedFile &&
			minimizedFileName &&
			onRestoreFile &&
			onDeleteFile ? (
				// Show minimized file card only
				<Card className="p-4 bg-accent/10 border-accent">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-3">
							<FileText className="h-5 w-5 text-accent" />
							<div>
								<p className="text-sm font-medium text-foreground">
									{minimizedFileName}
								</p>
								<p className="text-xs text-muted-foreground">
									Document minimized
								</p>
							</div>
						</div>
						<div className="flex gap-2">
							<Button variant="default" size="sm" onClick={onRestoreFile}>
								View
							</Button>
							<Button
								variant="ghost"
								size="sm"
								onClick={onDeleteFile}
								className="text-destructive hover:text-destructive"
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						</div>
					</div>
				</Card>
			) : (
				// Show upload area only when no file exists
				<Card
					onDrop={handleDrop}
					onDragOver={handleDragOver}
					className="border-2 border-dashed border-primary/30 hover:border-primary/60 transition-colors cursor-pointer bg-muted/30"
				>
					<label className="flex flex-col items-center justify-center p-8 cursor-pointer">
						<Upload className="h-12 w-12 text-primary mb-4" />
						<p className="text-sm font-medium text-foreground mb-1">
							Drop your document here or click to upload
						</p>
						<p className="text-xs text-muted-foreground">{descriptionText}</p>
						<input
							type="file"
							className="hidden"
							accept={acceptTypes}
							onChange={handleFileInput}
						/>
					</label>
				</Card>
			)}
		</div>
	);
};

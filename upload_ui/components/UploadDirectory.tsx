"use client";
import React, { useState } from 'react';

export type StageStatus = "IDLE" | "VALIDATING" | "SELECTED" | "REJECTED" | "ERROR";

const FORMAT_LIMITS: Record<string, { maxBytes: number; label: string }> = {
    pdf: { maxBytes: 10 * 1024 * 1024, label: "10 MB" },
    docx: { maxBytes: 5 * 1024 * 1024, label: "5 MB" },
    txt: { maxBytes: 512 * 1024, label: "512 KB" },
};

async function computeSha256(file: File): Promise<string> {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
    return Array.from(new Uint8Array(hashBuffer)).map((b) => b.toString().padStart(2, "0")).join("");
};


export default function UploadDirectory() {
    const [status, setStatus] = useState<StageStatus>("IDLE");
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [fileInfo, setFileInfo] = useState<{
        name: string;
        sizeKb: string;
        ext: string;
        sha256: string;
    } | null>(null);
    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setErrorMessage(null);
        setFileInfo(null);
        setStatus("VALIDATING");

        // Extension check
        const ext = file.name.split(".").pop()?.toLowerCase() || "";
        const rule = FORMAT_LIMITS[ext];

        if (!rule) {
            setStatus("REJECTED");
            setErrorMessage(`Unsupported format ".${ext}". Allowed: PDF, DOCX, TXT.`);
            setFileInfo(null);
            return;
        }

        if (file.size === 0 || file.size > rule.maxBytes) {
            setStatus("REJECTED");
            setErrorMessage(
                file.size === 0
                    ? "File is empty (0 bytes)."
                    : `${ext.toUpperCase()} exceeds the ${rule.label} limit.`
            );
            setFileInfo(null);
            return;
        }

        try {
            const sha256 = await computeSha256(file);
            setFileInfo({
                name: file.name,
                sizeKb: (file.size / 1024).toFixed(1),
                ext: ext.toUpperCase(),
                sha256
            });
            setStatus("SELECTED");
        } catch {
            setStatus("ERROR");
            setErrorMessage("Unable to calculate the file fingerprint in this browser.");
        }
    }

    return (
        <div className="max-w-xl mx-auto p-6 bg-white border-gray-200 rounded-xl shadow-sm space-y-6">
            {/* Dropzone input */}
            <label className='flex flex-col items-center justify-center w-full h-36 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:bg-gray-100 transition'>
                <span className="text-sm font-medium text-gray-700">
                    Click to select a PDF, DOCX, or TXT file
                </span>
                <span className="text-xs text-gray-500 mt-1">
                    Limits: PDF (10 MB) · DOCX (5 MB) · TXT (512 KB)
                </span>
                <input
                    type="file"
                    accept='.pdf,.docx,.txt'
                    onChange={handleFileChange}
                    className="hidden"
                />
            </label>

            {/* Status & Metadata Output */}
            {status !== "IDLE" && (
                <div className="p-4 rounded-lg border bg-gray-50 space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-700">Stage 1 Status:</span>
                        <span
                            className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${status === "SELECTED"
                                    ? "bg-green-100 text-green-800"
                                    : status === "REJECTED" || status === "ERROR"
                                        ? "bg-red-100 text-red-800"
                                        : "bg-blue-100 text-blue-800"
                                }`}
                        >
                            {status}
                        </span>
                    </div>

                    {errorMessage && (
                        <p className="text-red-600 text-xs font-medium">{errorMessage}</p>
                    )}

                    {fileInfo && (
                        <div className="pt-2 border-t border-gray-200 space-y-1 text-xs text-gray-600">
                            <p>
                                <strong>File:</strong> {fileInfo.name} ({fileInfo.sizeKb} KB ·{" "}
                                {fileInfo.ext})
                            </p>
                            <p className="break-all">
                                <strong>SHA-256:</strong>{" "}
                                <code className="bg-gray-200 px-1 rounded">
                                    {fileInfo.sha256}
                                </code>
                            </p>
                        </div>
                    )}
                </div>
            )}


        </div>

    );
}
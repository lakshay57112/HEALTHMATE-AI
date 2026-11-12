"use client";
import { PageHeader } from "@/components/common";
import { UploadPanel } from "@/components/upload";

export default function NewDocumentPage() {
  return (
    <>
      <PageHeader eyebrow="Document intelligence" title="Upload a document" description="Upload once — HealthMate reads it, explains it, and updates your medicines, reports, diet and appointments after you confirm." back="/app" />
      <UploadPanel />
    </>
  );
}

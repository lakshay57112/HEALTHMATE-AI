"use client";
import { PageHeader } from "@/components/common";
import { UploadPanel } from "@/components/upload";

export default function ReportUploadPage() {
  return (
    <>
      <PageHeader eyebrow="Medical reports" title="Upload a lab report" description="We'll read every test value and explain it in simple English or Hindi. Values and ranges are only ever taken from your report." back="/app/reports" />
      <UploadPanel defaultType="lab_report" lockType />
    </>
  );
}

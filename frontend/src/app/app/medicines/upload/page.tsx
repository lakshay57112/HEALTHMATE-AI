"use client";
import { PageHeader } from "@/components/common";
import { UploadPanel } from "@/components/upload";

export default function PrescriptionUploadPage() {
  return (
    <>
      <PageHeader eyebrow="Medicines" title="Upload a prescription" description="We'll find each medicine, its dose and timing. You check everything before reminders are created — we never guess a medicine or dose." back="/app/medicines" />
      <UploadPanel defaultType="prescription" lockType />
    </>
  );
}

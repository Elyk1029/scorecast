import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "cn";

export default function NotFound() {
  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Missing"
        title="That page is not on the slate"
        lede="The week or game is not in this forecast file."
      />
      <Link href="/" className={cn(buttonVariants())}>
        Back to this week
      </Link>
    </div>
  );
}

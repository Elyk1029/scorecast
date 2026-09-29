import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatSigned } from "@/lib/format";
import { getSeason } from "@/lib/season";

export const metadata: Metadata = {
  title: "Learned",
};

export default function LearnedPage() {
  const file = getSeason();
  const weeks = [...file.learned].reverse();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Learned"
        title="What moved"
        lede="Offense ratings in plain language, after the week was already played. A forecast never uses the game it is trying to call. Small moves are still moves."
      />
      <Card size="sm">
        <CardHeader>
          <CardDescription>Home field right now</CardDescription>
          <CardTitle className="font-display text-4xl text-forecast">
            {formatSigned(file.homeField)}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Fit from earlier non-neutral games only. Neutral sites get none of it.
          </p>
        </CardContent>
      </Card>
      {weeks.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No moves yet</CardTitle>
            <CardDescription>
              Rating notes show up here after a week has final games.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <ol className="space-y-3">
          {weeks.map((week) => (
            <li key={`${week.season}-${week.week}`}>
              <Card>
                <CardHeader>
                  <CardTitle>
                    Week {week.week}
                    <span className="ml-2 text-sm font-normal text-muted-foreground">
                      {week.season}
                    </span>
                  </CardTitle>
                  <CardDescription>
                    Home field after this week {formatSigned(week.homeField)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm leading-6">
                    {week.sentences.map((sentence) => (
                      <li key={sentence}>{sentence}</li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

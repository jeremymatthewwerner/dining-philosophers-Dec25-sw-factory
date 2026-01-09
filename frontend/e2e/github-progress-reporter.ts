/**
 * Custom Playwright reporter that updates a GitHub issue comment with real-time E2E test progress.
 *
 * Required environment variables:
 * - GH_TOKEN: GitHub token for API access
 * - GH_REPO: Repository in owner/repo format
 * - CI_COMMENT_ID: ID of the comment to update
 *
 * Usage in playwright.config.ts:
 *   reporter: process.env.CI_COMMENT_ID
 *     ? [['html'], ['json', {...}], ['./e2e/github-progress-reporter.ts']]
 *     : 'html'
 */

import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";

interface FileProgress {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  status: "pending" | "running" | "passed" | "failed";
}

class GitHubProgressReporter implements Reporter {
  private token: string;
  private repo: string;
  private commentId: string;
  private enabled: boolean;
  private fileProgress: Map<string, FileProgress> = new Map();
  private totalTests = 0;
  private completedTests = 0;
  private lastUpdateTime = 0;
  private updateInterval = 5000; // Minimum 5 seconds between updates (rate limit protection)
  private pendingUpdate = false;

  constructor() {
    this.token = process.env.GH_TOKEN || "";
    this.repo = process.env.GH_REPO || "";
    this.commentId = process.env.CI_COMMENT_ID || "";
    this.enabled = Boolean(this.token && this.repo && this.commentId);

    if (this.enabled) {
      console.log(
        `[GitHubProgressReporter] Enabled - updating comment ${this.commentId}`
      );
    } else {
      console.log(
        `[GitHubProgressReporter] Disabled - missing required env vars`
      );
    }
  }

  onBegin(_config: FullConfig, suite: Suite) {
    // Count total tests and initialize file tracking
    const countTests = (s: Suite): number => {
      let count = s.tests.length;
      for (const child of s.suites) {
        count += countTests(child);
      }
      return count;
    };

    this.totalTests = countTests(suite);

    // Initialize file progress for each top-level suite (test file)
    for (const fileSuite of suite.suites) {
      const fileName = this.getFileName(fileSuite.title);
      const fileTestCount = countTests(fileSuite);
      this.fileProgress.set(fileName, {
        total: fileTestCount,
        passed: 0,
        failed: 0,
        skipped: 0,
        duration: 0,
        status: "pending",
      });
    }

    console.log(
      `[GitHubProgressReporter] Starting ${this.totalTests} tests across ${this.fileProgress.size} files`
    );
  }

  onTestBegin(test: TestCase) {
    const fileName = this.getFileName(test.titlePath()[0] || "");
    const progress = this.fileProgress.get(fileName);
    if (progress && progress.status === "pending") {
      progress.status = "running";
      this.scheduleUpdate();
    }
  }

  onTestEnd(test: TestCase, result: TestResult) {
    this.completedTests++;
    const fileName = this.getFileName(test.titlePath()[0] || "");
    const progress = this.fileProgress.get(fileName);

    if (progress) {
      progress.duration += result.duration;

      if (result.status === "passed") {
        progress.passed++;
      } else if (result.status === "failed" || result.status === "timedOut") {
        progress.failed++;
      } else if (result.status === "skipped") {
        progress.skipped++;
      }

      // Check if file is complete
      const completed = progress.passed + progress.failed + progress.skipped;
      if (completed >= progress.total) {
        progress.status = progress.failed > 0 ? "failed" : "passed";
      }
    }

    this.scheduleUpdate();
  }

  async onEnd(_result: FullResult) {
    // Force final update
    await this.updateComment(true);
  }

  private getFileName(path: string): string {
    return path.split("/").pop() || path;
  }

  private scheduleUpdate() {
    if (!this.enabled || this.pendingUpdate) return;

    const now = Date.now();
    const timeSinceLastUpdate = now - this.lastUpdateTime;

    if (timeSinceLastUpdate >= this.updateInterval) {
      // Update immediately
      this.updateComment(false);
    } else {
      // Schedule update for later
      this.pendingUpdate = true;
      setTimeout(() => {
        this.pendingUpdate = false;
        this.updateComment(false);
      }, this.updateInterval - timeSinceLastUpdate);
    }
  }

  private async updateComment(force: boolean) {
    if (!this.enabled) return;

    const now = Date.now();
    if (!force && now - this.lastUpdateTime < this.updateInterval) {
      return;
    }
    this.lastUpdateTime = now;

    try {
      const body = this.generateCommentBody();
      const response = await fetch(
        `https://api.github.com/repos/${this.repo}/issues/comments/${this.commentId}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${this.token}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ body }),
        }
      );

      if (!response.ok) {
        console.error(
          `[GitHubProgressReporter] API error: ${response.status} ${response.statusText}`
        );
      }
    } catch (error) {
      console.error(`[GitHubProgressReporter] Update failed:`, error);
    }
  }

  private generateCommentBody(): string {
    const lines: string[] = [
      "<!-- ci-watcher -->",
      "## 🔄 CI Status",
      "",
      `**Status:** 🔄 **Running E2E Tests:** ${this.completedTests}/${this.totalTests} tests complete`,
      "",
      "| Test File | Status | Duration |",
      "|-----------|--------|----------|",
    ];

    // Sort files: running first, then by name
    const sortedFiles = [...this.fileProgress.entries()].sort((a, b) => {
      if (a[1].status === "running" && b[1].status !== "running") return -1;
      if (b[1].status === "running" && a[1].status !== "running") return 1;
      return a[0].localeCompare(b[0]);
    });

    for (const [fileName, progress] of sortedFiles) {
      const icon = this.getStatusIcon(progress);
      const statusText = this.getStatusText(progress);
      const duration = this.formatDuration(progress.duration);
      lines.push(`| ↳ ${fileName} | ${icon} ${statusText} | ${duration} |`);
    }

    lines.push("");
    lines.push(`*Last updated: ${new Date().toISOString().replace("T", " ").split(".")[0]} UTC*`);

    return lines.join("\n");
  }

  private getStatusIcon(progress: FileProgress): string {
    switch (progress.status) {
      case "pending":
        return "⏳";
      case "running":
        return "🔄";
      case "passed":
        return "✅";
      case "failed":
        return "❌";
      default:
        return "❓";
    }
  }

  private getStatusText(progress: FileProgress): string {
    const completed = progress.passed + progress.failed + progress.skipped;
    if (progress.status === "pending") {
      return `0/${progress.total} waiting`;
    }
    if (progress.status === "running") {
      return `${completed}/${progress.total} running`;
    }
    const failText = progress.failed > 0 ? ` (${progress.failed} failed)` : "";
    return `${progress.passed}/${progress.total} passed${failText}`;
  }

  private formatDuration(ms: number): string {
    if (ms === 0) return "-";
    const seconds = Math.round(ms / 100) / 10;
    return `${seconds}s`;
  }
}

export default GitHubProgressReporter;

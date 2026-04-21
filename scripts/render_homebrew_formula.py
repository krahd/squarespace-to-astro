from __future__ import annotations

import argparse


def build_formula(
    *,
    version: str,
    macos_arm64_sha256: str,
    linux_x86_64_sha256: str,
) -> str:
    return f"""class S2a < Formula
  desc "Migrate Squarespace sites into Astro-ready static content"
  homepage "https://github.com/krahd/squarespace-to-astro"
  version "{version}"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/krahd/squarespace-to-astro/releases/download/v#{{version}}/s2a-#{{version}}-macos-arm64.tar.gz"
      sha256 "{macos_arm64_sha256}"
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/krahd/squarespace-to-astro/releases/download/v#{{version}}/s2a-#{{version}}-linux-x86_64.tar.gz"
      sha256 "{linux_x86_64_sha256}"
    end
  end

  def install
    if OS.mac? && Hardware::CPU.intel?
      odie "Homebrew installation is not yet available for macOS Intel. Use the GitHub release archive instead."
    end

    if OS.linux? && !Hardware::CPU.intel?
      odie "Homebrew installation is currently available only for Linux x86_64. Use the GitHub release archive instead."
    end

    archive_name = if OS.mac?
      "s2a-#{{version}}-macos-arm64.tar.gz"
    else
      "s2a-#{{version}}-linux-x86_64.tar.gz"
    end

    pkgshare.install cached_download => archive_name

    (bin/"s2a").write <<~SH
      #!/bin/bash
      set -euo pipefail

      archive="#{'{'}opt_pkgshare{'}'}/#{'{'}archive_name{'}'}"

      if [[ "$(uname -s)" == "Darwin" ]]; then
        cache_root="$HOME/Library/Caches/s2a/homebrew/#{{version}}"
      else
        cache_root="${{XDG_CACHE_HOME:-$HOME/.cache}}/s2a/homebrew/#{{version}}"
      fi

      mkdir -p "$cache_root"
      bundle_dir=$(find "$cache_root" -mindepth 1 -maxdepth 1 -type d -name 's2a-*' | head -n 1)

      if [[ -z "$bundle_dir" ]]; then
        tar -xzf "$archive" -C "$cache_root"
        bundle_dir=$(find "$cache_root" -mindepth 1 -maxdepth 1 -type d -name 's2a-*' | head -n 1)
      fi

      if [[ -z "$bundle_dir" || ! -x "$bundle_dir/s2a" ]]; then
        echo "s2a bundle extraction failed" >&2
        exit 1
      fi

      exec "$bundle_dir/s2a" "$@"
    SH

    chmod 0755, bin/"s2a"
  end

  test do
    assert_match "Probe, extract, and generate", shell_output("#{{bin}}/s2a --help")
  end
end
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Homebrew formula for s2a.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--macos-arm64-sha256", required=True)
    parser.add_argument("--linux-x86-64-sha256", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    formula = build_formula(
        version=args.version,
        macos_arm64_sha256=args.macos_arm64_sha256,
        linux_x86_64_sha256=args.linux_x86_64_sha256,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(formula)
    else:
        print(formula, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";

const legacy = ["am", "bient"].join("");

test("tracked paths and text contain no former brand", () => {
  const paths = execFileSync("git", ["ls-files"], { encoding: "utf8" })
    .trim()
    .split("\n")
    .filter(Boolean);
  const names = paths.join("\n");
  const contents = paths
    .filter(path => !/\.(?:png|mp4)$/i.test(path))
    .map(path => readFileSync(path, "utf8"))
    .join("\n");
  assert.equal(names.toLowerCase().includes(legacy), false);
  assert.equal(contents.toLowerCase().includes(legacy), false);
});

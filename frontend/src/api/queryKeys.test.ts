import { describe, expect, it } from "vitest";

import { queryKeys } from "./queryKeys";

describe("queryKeys", () => {
  it("keeps campaign list and detail keys in the same namespace", () => {
    expect(queryKeys.campaigns).toEqual(["campaigns"]);
    expect(queryKeys.campaign("campaign-id")).toEqual(["campaigns", "campaign-id"]);
  });
});

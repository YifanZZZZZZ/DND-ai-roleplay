import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell/AppShell";
import { CampaignDetailPage } from "../pages/CampaignDetailPage";
import { CampaignsPage } from "../pages/CampaignsPage";
import { CharactersPage } from "../pages/CharactersPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { SessionPlayPage } from "../pages/SessionPlayPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate replace to="/campaigns" />} />
        <Route path="/campaigns" element={<CampaignsPage />} />
        <Route path="/campaigns/:campaignId" element={<CampaignDetailPage />} />
        <Route path="/campaigns/:campaignId/play" element={<SessionPlayPage />} />
        <Route path="/characters" element={<CharactersPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

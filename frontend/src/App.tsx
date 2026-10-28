import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { refreshReference } from "./data";
import { I18nProvider } from "./i18n";
import { Admin } from "./screens/Admin";
import { AssessmentLayout, AssessmentIndex } from "./screens/AssessmentLayout";
import { Declare } from "./screens/Declare";
import { Home } from "./screens/Home";
import { Mapping } from "./screens/Mapping";
import { ProfileScreen } from "./screens/ProfileScreen";
import { Queue } from "./screens/Queue";
import { Rater } from "./screens/Rater";
import { Scoring } from "./screens/Scoring";
import { Tasks } from "./screens/Tasks";
import { SettingsProvider } from "./settings";
import { startSyncLoop } from "./sync";

export function App() {
  useEffect(() => {
    const stop = startSyncLoop();
    void refreshReference(true);
    return stop;
  }, []);
  return (
    <I18nProvider>
      <SettingsProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Home />} />
              <Route path="declare" element={<Declare />} />
              <Route path="a/:id" element={<AssessmentLayout />}>
                <Route index element={<AssessmentIndex />} />
                <Route path="mapping" element={<Mapping />} />
                <Route path="tasks" element={<Tasks />} />
                <Route path="score" element={<Scoring />} />
                <Route path="profile" element={<ProfileScreen />} />
              </Route>
              <Route path="admin" element={<Admin />} />
              <Route path="rater" element={<Rater />} />
              <Route path="queue" element={<Queue />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </SettingsProvider>
    </I18nProvider>
  );
}

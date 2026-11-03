import { useEffect } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import type { AccountRole } from "./api";
import { api } from "./api";
import { Layout } from "./components/Layout";
import { refreshReference } from "./data";
import { hasChosenLanguage, I18nProvider } from "./i18n";
import { Admin } from "./screens/Admin";
import { AssessmentIndex, AssessmentLayout } from "./screens/AssessmentLayout";
import { BookingsScreen } from "./screens/Bookings";
import { FindWorkers, WorkerDetail } from "./screens/customer/Find";
import { Declare } from "./screens/Declare";
import { Home } from "./screens/Home";
import { LanguageScreen } from "./screens/LanguageScreen";
import { Login } from "./screens/Login";
import { Mapping } from "./screens/Mapping";
import { Onboarding } from "./screens/Onboarding";
import { PrivacyScreen } from "./screens/Privacy";
import { ProfileScreen } from "./screens/ProfileScreen";
import { Queue } from "./screens/Queue";
import { Rater } from "./screens/Rater";
import { ResetPin } from "./screens/ResetPin";
import { Scoring } from "./screens/Scoring";
import { Settings } from "./screens/Settings";
import { Permits } from "./screens/staff/Permits";
import { Requests } from "./screens/staff/Requests";
import { Tasks } from "./screens/Tasks";
import { AssessRequestScreen } from "./screens/worker/AssessRequest";
import { WorkerProfile } from "./screens/worker/Profile";
import { QuizHome, QuizReview, QuizRun } from "./screens/worker/Quiz";
import { getSession, homePath, quizPending, STAFF_ROLES, updateAccount, useSession } from "./session";
import { isConnected } from "./status";
import { startSyncLoop } from "./sync";

/** Only these roles may see the nested routes; others go to their own home, guests to login. */
function RequireRole({ roles }: { roles?: AccountRole[] }) {
  const { account, next } = useSession();
  const location = useLocation();
  if (!account) {
    if (next) return <Navigate to={next} replace />; // logged out or erased on purpose
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (roles && !roles.includes(account.role)) return <Navigate to={homePath(account)} replace />;
  return <Outlet />;
}

/** The quiz is compulsory for workers: until one is finished, these screens send them back to it.
 * The server refuses the same actions (profile, listing, assessment request). */
function RequireQuiz() {
  const { account } = useSession();
  if (quizPending(account)) return <Navigate to={homePath(account)} replace />;
  return <Outlet />;
}

function RootRedirect() {
  const { account } = useSession();
  if (account) return <Navigate to={homePath(account)} replace />;
  return <Navigate to={hasChosenLanguage() ? "/welcome?step=role" : "/welcome"} replace />;
}

const ASSESSORS: AccountRole[] = ["assessor", "admin"];

export function App() {
  useEffect(() => {
    const stop = startSyncLoop();
    void refreshReference(true);
    // Refresh the account (consents can change on another device); a 401 ends the session.
    if (getSession().token && isConnected()) void api.me().then(updateAccount).catch(() => undefined);
    return stop;
  }, []);
  return (
    <I18nProvider>
      <BrowserRouter>
        <Routes>
          <Route path="welcome" element={<Onboarding />} />
          <Route path="login" element={<Login />} />
          <Route path="reset-pin" element={<ResetPin />} />
          <Route path="language" element={<LanguageScreen />} />
          <Route element={<Layout />}>
            <Route index element={<RootRedirect />} />

            {/* Worker */}
            <Route path="w" element={<RequireRole roles={["worker"]} />}>
              <Route index element={<Navigate to="quiz" replace />} />
              <Route path="quiz" element={<QuizHome />} />
              <Route path="quiz/:id" element={<QuizRun />} />
              <Route path="quiz/:id/review" element={<QuizReview />} />
              <Route element={<RequireQuiz />}>
                <Route path="profile" element={<WorkerProfile />} />
                <Route path="assess" element={<AssessRequestScreen />} />
                <Route path="bookings" element={<BookingsScreen />} />
              </Route>
              <Route path="privacy" element={<PrivacyScreen />} />
            </Route>

            {/* Customer: searching is open to everyone, booking needs a customer login */}
            <Route path="c">
              <Route index element={<Navigate to="find" replace />} />
              <Route path="find" element={<FindWorkers />} />
              <Route path="worker/:id" element={<WorkerDetail />} />
              <Route element={<RequireRole roles={["customer"]} />}>
                <Route path="bookings" element={<BookingsScreen />} />
                <Route path="privacy" element={<PrivacyScreen />} />
              </Route>
            </Route>

            <Route element={<RequireRole />}>
              <Route path="settings" element={<Settings />} />
            </Route>

            {/* Staff: the assessor-side screens */}
            <Route element={<RequireRole roles={STAFF_ROLES} />}>
              <Route path="staff" element={<Home />} />
              <Route path="declare" element={<Declare />} />
              <Route path="a/:id" element={<AssessmentLayout />}>
                <Route index element={<AssessmentIndex />} />
                <Route path="mapping" element={<Mapping />} />
                <Route path="tasks" element={<Tasks />} />
                <Route path="score" element={<Scoring />} />
                <Route path="profile" element={<ProfileScreen />} />
              </Route>
              <Route path="queue" element={<Queue />} />
            </Route>
            <Route element={<RequireRole roles={ASSESSORS} />}>
              <Route path="staff/requests" element={<Requests />} />
              <Route path="admin" element={<Admin />} />
            </Route>
            <Route element={<RequireRole roles={["admin"]} />}>
              <Route path="staff/permits" element={<Permits />} />
            </Route>
            {/* Rater study: open endpoints, no login needed */}
            <Route path="rater" element={<Rater />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </I18nProvider>
  );
}

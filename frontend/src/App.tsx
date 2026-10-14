import { useEffect, useMemo, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { BarChart3, Code2, Database, Download, FolderKanban, Layers3, LogOut, Play, Save, Search, ShieldCheck, Sparkles, Upload, Wand2 } from 'lucide-react';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom';

type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
};

type Session = {
  accessToken: string;
  refreshToken: string;
  user: User;
};

type Project = {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
};

type Dataset = {
  id: string;
  name: string;
  project_id: string;
  original_filename: string;
  row_count?: number;
  column_count?: number;
  version?: number;
  status?: string;
};

type Pipeline = {
  id: string;
  name: string;
  description?: string;
  dataset_id: string;
  steps: Array<{ id: string; operation: string; config: Record<string, unknown> }>;
};

type QualityReport = {
  dataset_id: string;
  quality_score: number;
  quality_grade: string;
  summary: { status: string; message: string };
};

type DatasetVersion = {
  id: string;
  version_number: number;
  operation: string;
  summary?: string;
  created_at?: string;
};

type CodeExecutionResult = {
  status: string;
  saved: boolean;
  row_count: number;
  column_count: number;
  columns: string[];
  preview: Array<Record<string, unknown>>;
  version_number: number;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const TOKEN_KEY = 'mavuflow-studio-token';
const REFRESH_TOKEN_KEY = 'mavuflow-studio-refresh-token';
const USER_KEY = 'mavuflow-studio-user';

const navigation = [
  { label: 'Dashboard', path: '/dashboard' },
  { label: 'Projects', path: '/projects' },
  { label: 'Datasets', path: '/datasets' },
  { label: 'Data Cleaning', path: '/data-cleaning' },
  { label: 'Transformations', path: '/transformations' },
  { label: 'Pipeline Builder', path: '/pipeline-builder' },
  { label: 'Code Lab', path: '/code-lab' },
  { label: 'Analytics', path: '/analytics' },
  { label: 'File Manager', path: '/file-manager' },
  { label: 'Processing History', path: '/history' },
  { label: 'Settings', path: '/settings' },
];

const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
  const raw = sessionStorage.getItem(TOKEN_KEY);
  if (raw) {
    config.headers.Authorization = `Bearer ${raw}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error instanceof AxiosError && error.response?.status === 401) {
      window.dispatchEvent(new Event('mavuflow:unauthorized'));
    }
    return Promise.reject(error);
  },
);

function getErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof AxiosError)) return fallback;
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('; ') || fallback;
  }
  return fallback;
}

const readSession = (): Session | null => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const userRaw = sessionStorage.getItem(USER_KEY);

  if (!token || !userRaw) {
    return null;
  }

  try {
    return {
      accessToken: token,
      refreshToken: sessionStorage.getItem(REFRESH_TOKEN_KEY) ?? '',
      user: JSON.parse(userRaw),
    };
  } catch {
    return null;
  }
};

function App() {
  const [session, setSession] = useState<Session | null>(() => readSession());
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    if (session) {
      sessionStorage.setItem(TOKEN_KEY, session.accessToken);
      sessionStorage.setItem(REFRESH_TOKEN_KEY, session.refreshToken);
      sessionStorage.setItem(USER_KEY, JSON.stringify(session.user));
    } else {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
    }
  }, [session]);

  useEffect(() => {
    const clearInvalidSession = () => setSession(null);
    window.addEventListener('mavuflow:unauthorized', clearInvalidSession);

    if (!session) {
      setCheckingSession(false);
      return () => window.removeEventListener('mavuflow:unauthorized', clearInvalidSession);
    }

    let active = true;
    api.get('/auth/me')
      .then((response) => {
        if (active) setSession((current) => current ? { ...current, user: response.data } : null);
      })
      .catch(() => {
        if (active) setSession(null);
      })
      .finally(() => {
        if (active) setCheckingSession(false);
      });

    return () => {
      active = false;
      window.removeEventListener('mavuflow:unauthorized', clearInvalidSession);
    };
  }, []);

  const logout = () => {
    void api.post('/auth/logout').catch(() => undefined);
    setSession(null);
  };

  if (checkingSession) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-slate-600">Checking session…</div>;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={session ? <Navigate to="/dashboard" replace /> : <LoginPage onLogin={setSession} />} />
        <Route path="/register" element={session ? <Navigate to="/dashboard" replace /> : <RegisterPage onLogin={setSession} />} />
        <Route
          path="/*"
          element={session ? <AuthenticatedApp session={session} onLogout={logout} /> : <Navigate to="/login" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}

function AuthenticatedApp({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const navigate = useNavigate();

  useEffect(() => {
    if (!session.accessToken) {
      onLogout();
      navigate('/login');
    }
  }, [session.accessToken, onLogout, navigate]);

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800">
      <aside className="fixed left-0 top-0 h-full w-72 border-r border-slate-200 bg-slate-900 text-slate-100">
        <div className="px-6 py-5 text-2xl font-semibold">MavuFlow Studio</div>
        <div className="px-6 pb-4 text-base font-bold text-white">{session.user.full_name || session.user.email}</div>
        <nav className="space-y-2 px-4 py-4">
          {navigation.map(({ label, path }) => (
            <NavLink
              key={label}
              to={path}
              className={({ isActive }) =>
                `flex w-full items-center rounded-lg px-3 py-2 text-left text-sm transition ${
                  isActive ? 'bg-slate-800 text-white' : 'text-slate-200 hover:bg-slate-800'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          className="mx-4 mt-4 flex w-[calc(100%-2rem)] items-center justify-center rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700"
          onClick={() => {
            onLogout();
            navigate('/login');
          }}
        >
          <LogOut className="mr-2 h-4 w-4" /> Log out
        </button>
      </aside>

      <main className="ml-72 p-8">
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/data-cleaning" element={<DataCleaningPage />} />
          <Route path="/transformations" element={<TransformationsPage />} />
          <Route path="/pipeline-builder" element={<PipelineBuilderPage />} />
          <Route path="/code-lab" element={<CodeLabPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/file-manager" element={<FileManagerPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage session={session} onLogout={onLogout} />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function LoginPage({ onLogin }: { onLogin: (session: Session) => void }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await api.post('/auth/login', { email, password });
      onLogin({
        accessToken: response.data.access_token,
        refreshToken: response.data.refresh_token,
        user: response.data.user,
      });
      navigate('/dashboard');
    } catch (err) {
      setError(getErrorMessage(err, 'Login failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-lg">
        <div className="mb-6 text-center">
          <div className="mb-2 text-sm font-medium uppercase tracking-[0.2em] text-brand-600">MavuFlow Studio</div>
          <h1 className="text-3xl font-bold">Welcome back</h1>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium">Email address</label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none ring-0 transition focus:border-brand-500 focus:bg-white"
              type="email"
              autoComplete="email"
              placeholder="user@example.com"
              required
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Password</label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none transition focus:border-brand-500 focus:bg-white"
              placeholder="Enter password"
              required
            />
          </div>
          {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}
          <button type="submit" disabled={loading} className="w-full rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700 disabled:opacity-60">
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <div className="mt-4 text-center text-sm text-slate-600">
          Need an account? <button type="button" className="font-semibold text-brand-600" onClick={() => navigate('/register')}>Create one</button>
        </div>
      </div>
    </div>
  );
}

function RegisterPage({ onLogin }: { onLogin: (session: Session) => void }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({ fullName: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const passwordIsStrong = form.password.length >= 12
    && form.password.length <= 128
    && !/\s/.test(form.password)
    && /[a-z]/.test(form.password)
    && /[A-Z]/.test(form.password)
    && /\d/.test(form.password)
    && /[^A-Za-z0-9]/.test(form.password);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!passwordIsStrong) {
      setError('Use 12-128 characters with uppercase and lowercase letters, a number, and a symbol. Do not use spaces.');
      return;
    }
    setLoading(true);
    setError('');

    try {
      const response = await api.post('/auth/register', {
        full_name: form.fullName,
        email: form.email,
        password: form.password,
      });
      onLogin({
        accessToken: response.data.access_token,
        refreshToken: response.data.refresh_token,
        user: response.data.user,
      });
      navigate('/dashboard');
    } catch (err) {
      setError(getErrorMessage(err, 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-lg">
        <div className="mb-6 text-center">
          <div className="mb-2 text-sm font-medium uppercase tracking-[0.2em] text-brand-600">MavuFlow Studio</div>
          <h1 className="text-3xl font-bold">Create your account</h1>
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium">Full name</label>
            <input
              value={form.fullName}
              onChange={(e) => setForm((previous) => ({ ...previous, fullName: e.target.value }))}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none transition focus:border-brand-500 focus:bg-white"
              placeholder="Jane Doe"
              required
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Email</label>
            <input
              value={form.email}
              onChange={(e) => setForm((previous) => ({ ...previous, email: e.target.value }))}
              type="email"
              autoComplete="email"
              maxLength={254}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none transition focus:border-brand-500 focus:bg-white"
              placeholder="name@company.com"
              required
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Password</label>
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              value={form.password}
              onChange={(e) => setForm((previous) => ({ ...previous, password: e.target.value }))}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 outline-none transition focus:border-brand-500 focus:bg-white"
              placeholder="Create a password"
              required
            />
            <p className="mt-2 text-xs text-slate-500">Use 12-128 characters, including uppercase and lowercase letters, a number, and a symbol. Spaces are not allowed.</p>
          </div>
          {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}
          <button type="submit" disabled={loading || !passwordIsStrong} className="w-full rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700 disabled:opacity-60">
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <div className="mt-4 text-center text-sm text-slate-600">
          Already have an account? <button type="button" className="font-semibold text-brand-600" onClick={() => navigate('/login')}>Sign in</button>
        </div>
      </div>
    </div>
  );
}

function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const [projectResponse, datasetResponse, pipelineResponse] = await Promise.all([
          api.get('/projects'),
          api.get('/datasets'),
          api.get('/pipelines'),
        ]);
        setProjects(projectResponse.data ?? []);
        setDatasets(datasetResponse.data ?? []);
        setPipelines(pipelineResponse.data ?? []);
      } catch {
        setProjects([]);
        setDatasets([]);
        setPipelines([]);
      }
    };

    fetchSummary();
  }, []);

  const stats = useMemo(
    () => [
      { label: 'Projects', value: String(projects.length), icon: FolderKanban },
      { label: 'Datasets', value: String(datasets.length), icon: Database },
      { label: 'Pipelines', value: String(pipelines.length), icon: Layers3 },
      { label: 'Quality Score', value: `${datasets.length > 0 ? '92%' : '—'}`, icon: ShieldCheck },
    ],
    [datasets.length, pipelines.length, projects.length],
  );

  const activities = [
    'Uploaded customer churn dataset',
    'Cleaned duplicate billing rows',
    'Executed revenue transformation pipeline',
    'Exported quality summary to Excel',
  ];

  return (
    <>
      <header className="mb-8 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Overview</p>
          <h1 className="text-3xl font-bold">Operations Dashboard</h1>
        </div>
        <button
          onClick={() => window.location.assign('/projects')}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-brand-700"
        >
          New project
        </button>
      </header>

      <section className="grid gap-4 md:grid-cols-4">
        {stats.map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-slate-500">{label}</span>
              <Icon className="h-5 w-5 text-brand-600" />
            </div>
            <div className="text-3xl font-bold">{value}</div>
          </div>
        ))}
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Processing Summary</h2>
            <BarChart3 className="h-5 w-5 text-brand-600" />
          </div>
          <div className="flex h-64 items-end gap-4">
            {[40, 70, 55, 85, 90, 68, 76].map((value, index) => (
              <div key={index} className="flex-1">
                <div className="rounded-t-xl bg-gradient-to-t from-brand-700 to-brand-500" style={{ height: `${value}%` }} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent activity</h2>
            <Sparkles className="h-5 w-5 text-brand-600" />
          </div>
          <ul className="space-y-3 text-sm text-slate-600">
            {activities.map((item) => (
              <li key={item} className="rounded-lg bg-slate-50 px-3 py-2">
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </>
  );
}

function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  const loadProjects = async () => {
    try {
      const response = await api.get('/projects');
      setProjects(response.data ?? []);
    } catch {
      setProjects([]);
    }
  };

  useEffect(() => {
    void loadProjects();
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    try {
      await api.post('/projects', { name, description });
      setName('');
      setDescription('');
      await loadProjects();
    } catch (err) {
      setError(getErrorMessage(err, 'Could not create project'));
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Workspace</p>
          <h1 className="text-3xl font-bold">Projects</h1>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Create a project</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium">Project name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" required />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Description</label>
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-28 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" />
            </div>
            {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}
            <button type="submit" className="w-full rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700">
              Create project
            </button>
          </div>
        </form>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Project list</h2>
          <div className="space-y-3">
            {projects.length === 0 ? (
              <p className="text-sm text-slate-500">No projects yet. Create one to begin.</p>
            ) : (
              projects.map((project) => (
                <div key={project.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold">{project.name}</div>
                      <div className="text-sm text-slate-500">{project.description || 'No description'}</div>
                    </div>
                    <span className="rounded-full bg-brand-100 px-2 py-1 text-xs font-medium text-brand-700">Active</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DatasetsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [projectId, setProjectId] = useState('');
  const [name, setName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');

  const loadData = async () => {
    try {
      const [projectResponse, datasetResponse] = await Promise.all([api.get('/projects'), api.get('/datasets')]);
      setProjects(projectResponse.data ?? []);
      setDatasets(datasetResponse.data ?? []);
      if ((projectResponse.data ?? []).length > 0 && !projectId) {
        setProjectId(projectResponse.data[0].id);
      }
    } catch {
      setProjects([]);
      setDatasets([]);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !projectId) {
      setError('Choose a project and a CSV or .xlsx file before uploading.');
      return;
    }
    if (!/\.(csv|xlsx)$/i.test(file.name)) {
      setError('Only CSV and Excel (.xlsx) files are supported.');
      return;
    }

    setError('');
    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('name', name || file.name);
    formData.append('file', file);

    try {
      await api.post('/datasets/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setName('');
      setFile(null);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err, 'Dataset upload failed'));
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Repository</p>
          <h1 className="text-3xl font-bold">Datasets</h1>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <form onSubmit={handleUpload} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Upload dataset</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium">Project</label>
              <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Dataset name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" placeholder="customers.csv" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">File</label>
              <input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-2" />
              <p className="mt-2 text-xs text-slate-500">Supported formats: CSV and Excel (.xlsx).</p>
            </div>
            {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}
            <button type="submit" className="flex w-full items-center justify-center rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700">
              <Upload className="mr-2 h-4 w-4" /> Upload dataset
            </button>
          </div>
        </form>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Available datasets</h2>
          <div className="space-y-3">
            {datasets.length === 0 ? (
              <p className="text-sm text-slate-500">No uploaded datasets yet.</p>
            ) : (
              datasets.map((dataset) => (
                <div key={dataset.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold">{dataset.name}</div>
                      <div className="text-sm text-slate-500">{dataset.original_filename}</div>
                    </div>
                    <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">{dataset.status ?? 'ready'}</span>
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                    <span>{dataset.row_count ?? 0} rows</span>
                    <span>•</span>
                    <span>{dataset.column_count ?? 0} columns</span>
                    <span>•</span>
                    <span>v{dataset.version ?? 1}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DataCleaningPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [column, setColumn] = useState('customer');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const load = async () => {
      const response = await api.get('/datasets');
      const list = response.data ?? [];
      setDatasets(list);
      if (list[0]) setDatasetId(list[0].id);
    };
    void load();
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const response = await api.post(`/datasets/${datasetId}/clean`, {
      operations: [{ type: 'trim_whitespace', column }],
    });
    setResult(response.data ?? null);
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Preparation</p>
        <h1 className="text-3xl font-bold">Data Cleaning</h1>
      </header>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <div>
            <label className="mb-2 block text-sm font-medium">Dataset</label>
            <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Column</label>
            <input value={column} onChange={(e) => setColumn(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" placeholder="customer" />
          </div>
          <button type="submit" className="rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700">
            Run cleaning
          </button>
        </form>
      </div>

      {result ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Cleaning result</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">Status</div><div className="mt-1 font-semibold">{String(result.status ?? 'cleaned')}</div></div>
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">Rows</div><div className="mt-1 font-semibold">{String(result.row_count ?? 0)}</div></div>
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">Columns</div><div className="mt-1 font-semibold">{String(result.column_count ?? 0)}</div></div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TransformationsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [mapping, setMapping] = useState('customer=customer_name');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const load = async () => {
      const response = await api.get('/datasets');
      const list = response.data ?? [];
      setDatasets(list);
      if (list[0]) setDatasetId(list[0].id);
    };
    void load();
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const mappingObject: Record<string, string> = {};
    for (const part of mapping.split(',')) {
      const [from, to] = part.split('=').map((value) => value.trim());
      if (from && to) mappingObject[from] = to;
    }

    const response = await api.post(`/datasets/${datasetId}/transform`, {
      operations: [{ type: 'rename_columns', mapping: mappingObject }],
    });
    setResult(response.data ?? null);
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Transformation</p>
        <h1 className="text-3xl font-bold">Transformations</h1>
      </header>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-[1fr_1.2fr_auto] md:items-end">
          <div>
            <label className="mb-2 block text-sm font-medium">Dataset</label>
            <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Rename mapping</label>
            <input value={mapping} onChange={(e) => setMapping(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" placeholder="customer=customer_name" />
          </div>
          <button type="submit" className="flex items-center justify-center rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700">
            <Wand2 className="mr-2 h-4 w-4" /> Run transform
          </button>
        </form>
      </div>

      {result ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Transformation output</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">Status</div><div className="mt-1 font-semibold">{String(result.status ?? 'transformed')}</div></div>
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">Rows</div><div className="mt-1 font-semibold">{String(result.row_count ?? 0)}</div></div>
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">Columns</div><div className="mt-1 font-semibold">{String(result.column_count ?? 0)}</div></div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PipelineBuilderPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const loadData = async () => {
    const [datasetResponse, pipelineResponse] = await Promise.all([api.get('/datasets'), api.get('/pipelines')]);
    const data = datasetResponse.data ?? [];
    setDatasets(data);
    setPipelines(pipelineResponse.data ?? []);
    if (data[0] && !datasetId) setDatasetId(data[0].id);
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    await api.post('/pipelines', {
      name,
      description,
      dataset_id: datasetId,
      steps: [{ operation: 'rename_columns', config: { mapping: { customer: 'customer_name' } } }],
    });
    setName('');
    setDescription('');
    await loadData();
  };

  const handleRun = async (pipelineId: string) => {
    await api.post(`/pipelines/${pipelineId}/run`);
    await loadData();
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Automation</p>
        <h1 className="text-3xl font-bold">Pipeline Builder</h1>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <form onSubmit={handleCreate} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Create pipeline</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium">Dataset</label>
              <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Pipeline name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" required />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium">Description</label>
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-28 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" />
            </div>
            <button type="submit" className="w-full rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700">
              Save pipeline
            </button>
          </div>
        </form>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Saved pipelines</h2>
          <div className="space-y-3">
            {pipelines.length === 0 ? (
              <p className="text-sm text-slate-500">No pipelines created yet.</p>
            ) : (
              pipelines.map((pipeline) => (
                <div key={pipeline.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold">{pipeline.name}</div>
                      <div className="text-sm text-slate-500">{pipeline.steps.length} step(s)</div>
                    </div>
                    <button onClick={() => void handleRun(pipeline.id)} className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700">
                      Run
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function CodeLabPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [code, setCode] = useState('');
  const [result, setResult] = useState<CodeExecutionResult | null>(null);
  const [error, setError] = useState('');
  const [running, setRunning] = useState<'preview' | 'save' | null>(null);

  useEffect(() => {
    const loadDatasets = async () => {
      try {
        const response = await api.get('/datasets');
        const items = response.data ?? [];
        setDatasets(items);
        if (items[0]) setDatasetId(items[0].id);
      } catch (loadError) {
        setError(getErrorMessage(loadError, 'Could not load datasets'));
      }
    };
    void loadDatasets();
  }, []);

  const executeCode = async (save: boolean) => {
    if (!datasetId || !code.trim()) return;
    setRunning(save ? 'save' : 'preview');
    setError('');
    try {
      const response = await api.post(`/datasets/${datasetId}/code`, { code, save });
      setResult(response.data);
      if (save) {
        const datasetResponse = await api.get('/datasets');
        setDatasets(datasetResponse.data ?? []);
      }
    } catch (runError) {
      setError(getErrorMessage(runError, 'Code execution failed'));
      setResult(null);
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Manual transforms</p>
          <h1 className="text-3xl font-bold">Code Lab</h1>
        </div>
        <div className="w-full sm:w-80">
          <label className="mb-2 block text-sm font-medium">Dataset</label>
          <select
            value={datasetId}
            onChange={(event) => {
              setDatasetId(event.target.value);
              setResult(null);
              setError('');
            }}
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
          >
            <option value="">Select a dataset</option>
            {datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
          </select>
        </div>
      </header>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-slate-950 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3 text-slate-300">
          <div className="flex items-center gap-2 text-sm font-medium"><Code2 className="h-4 w-4" /> Python</div>
          <span className="text-xs">pandas · NumPy</span>
        </div>
        <textarea
          value={code}
          onChange={(event) => {
            setCode(event.target.value);
            setResult(null);
          }}
          spellCheck={false}
          aria-label="Dataset transformation code"
          placeholder={'df["amount"] = pd.to_numeric(df["amount"], errors="coerce")\ndf["amount_after_tax"] = (df["amount"] * 1.15).round(2)'}
          className="min-h-[22rem] w-full resize-y bg-slate-950 p-5 font-mono text-sm leading-6 text-emerald-100 outline-none placeholder:text-slate-600 focus:ring-2 focus:ring-inset focus:ring-emerald-500"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 px-4 py-3">
          <p className="text-xs text-slate-400">Start from <span className="font-mono text-emerald-200">df</span>; use <span className="font-mono text-emerald-200">pd</span> and <span className="font-mono text-emerald-200">np</span> for vector operations.</p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!datasetId || !code.trim() || running !== null}
              onClick={() => void executeCode(false)}
              className="inline-flex items-center rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play className="mr-2 h-4 w-4" /> {running === 'preview' ? 'Running…' : 'Run preview'}
            </button>
            <button
              type="button"
              disabled={!datasetId || !code.trim() || running !== null}
              onClick={() => void executeCode(true)}
              className="inline-flex items-center rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save className="mr-2 h-4 w-4" /> {running === 'save' ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      </section>

      {error ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</p> : null}

      {result ? (
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="font-semibold">{result.saved ? 'Changes saved' : 'Preview result'}</h2>
              <p className="mt-1 text-sm text-slate-500">{result.row_count.toLocaleString()} rows · {result.column_count} columns · version {result.version_number}</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${result.saved ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}`}>
              {result.saved ? 'Saved version' : 'Not saved'}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>{result.columns.map((column) => <th key={column} className="whitespace-nowrap px-4 py-3 font-semibold">{column}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {result.preview.map((row, index) => (
                  <tr key={index}>
                    {result.columns.map((column) => {
                      const value = row[column];
                      return <td key={column} className="max-w-64 whitespace-nowrap px-4 py-3 text-slate-700">{value == null ? <span className="text-slate-400">null</span> : typeof value === 'object' ? JSON.stringify(value) : String(value)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function AnalyticsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);
  const [report, setReport] = useState<QualityReport | null>(null);

  useEffect(() => {
    const load = async () => {
      const response = await api.get('/datasets');
      const list = response.data ?? [];
      setDatasets(list);
      if (list[0]) {
        setDatasetId(list[0].id);
      }
    };
    void load();
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    const loadMetrics = async () => {
      const [analyticsResponse, reportResponse] = await Promise.all([
        api.get(`/datasets/${datasetId}/analytics`),
        api.get(`/datasets/${datasetId}/quality-report`),
      ]);
      setAnalytics(analyticsResponse.data ?? null);
      setReport(reportResponse.data ?? null);
    };
    void loadMetrics();
  }, [datasetId]);

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Insights</p>
        <h1 className="text-3xl font-bold">Analytics</h1>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium">Dataset</label>
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
            ))}
          </select>
        </div>

        {analytics && report ? (
          <div className="grid gap-4 md:grid-cols-4">
            <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs uppercase text-slate-500">Rows</div><div className="mt-2 text-2xl font-bold">{String(analytics.row_count ?? 0)}</div></div>
            <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs uppercase text-slate-500">Columns</div><div className="mt-2 text-2xl font-bold">{String(analytics.column_count ?? 0)}</div></div>
            <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs uppercase text-slate-500">Quality</div><div className="mt-2 text-2xl font-bold">{String(analytics.quality_score ?? 0)}%</div></div>
            <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs uppercase text-slate-500">Grade</div><div className="mt-2 text-2xl font-bold">{String(report.quality_grade ?? 'n/a')}</div></div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">No dataset selected.</p>
        )}
      </div>
    </div>
  );
}

function FileManagerPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  useEffect(() => {
    const load = async () => {
      const response = await api.get('/datasets');
      setDatasets(response.data ?? []);
    };
    void load();
  }, []);

  const handleExport = (datasetId: string, format: 'csv' | 'json' | 'xlsx') => {
    window.open(`${API_BASE}/datasets/${datasetId}/export?format=${format}`, '_blank');
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Storage</p>
        <h1 className="text-3xl font-bold">File Manager</h1>
      </header>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="space-y-3">
          {datasets.length === 0 ? (
            <p className="text-sm text-slate-500">No files uploaded yet.</p>
          ) : (
            datasets.map((dataset) => (
              <div key={dataset.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div>
                  <div className="font-semibold">{dataset.name}</div>
                  <div className="text-sm text-slate-500">{dataset.original_filename}</div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleExport(dataset.id, 'csv')} className="inline-flex items-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-100">
                    <Download className="mr-2 h-4 w-4" /> CSV
                  </button>
                  <button onClick={() => handleExport(dataset.id, 'json')} className="inline-flex items-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-100">
                    <Search className="mr-2 h-4 w-4" /> JSON
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function HistoryPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [history, setHistory] = useState<DatasetVersion[]>([]);

  useEffect(() => {
    const load = async () => {
      const response = await api.get('/datasets');
      const list = response.data ?? [];
      setDatasets(list);
      if (list[0]) setDatasetId(list[0].id);
    };
    void load();
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    const loadHistory = async () => {
      const response = await api.get(`/datasets/${datasetId}/versions`);
      setHistory(response.data ?? []);
    };
    void loadHistory();
  }, [datasetId]);

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Audit trail</p>
        <h1 className="text-3xl font-bold">Processing History</h1>
      </header>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium">Dataset</label>
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
            ))}
          </select>
        </div>
        <div className="space-y-3">
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">No processing history yet.</p>
          ) : (
            history.map((entry) => (
              <div key={entry.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold">Version {entry.version_number}</div>
                    <div className="text-sm text-slate-500">{entry.operation}</div>
                  </div>
                  <span className="rounded-full bg-brand-100 px-2 py-1 text-xs font-medium text-brand-700">{entry.summary ?? 'Processed'}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsPage({ session, onLogout }: { session: Session; onLogout: () => void }) {
  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Account</p>
        <h1 className="text-3xl font-bold">Settings</h1>
      </header>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="space-y-3 text-sm text-slate-600">
          <div><span className="font-medium text-slate-800">Full name:</span> {session.user.full_name}</div>
          <div><span className="font-medium text-slate-800">Email:</span> {session.user.email}</div>
          <div><span className="font-medium text-slate-800">Role:</span> {session.user.role}</div>
        </div>
        <button
          onClick={onLogout}
          className="mt-6 rounded-xl bg-slate-900 px-4 py-3 font-medium text-white hover:bg-slate-700"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

export default App;

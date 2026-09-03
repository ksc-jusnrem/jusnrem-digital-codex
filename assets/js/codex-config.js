/*
 * Supabase project configuration.
 *
 * Both values below are PUBLIC by design. The anon key is meant to be shipped to
 * the browser; it is protected by Row Level Security on the Supabase side, not by
 * secrecy. It is safe to commit.
 *
 * Never put the SERVICE ROLE key here. That one bypasses Row Level Security and
 * belongs only in a server environment variable.
 *
 * To fill these in: Supabase dashboard -> Project Settings -> API.
 *   url     = Project URL
 *   anonKey = Project API keys -> anon / public
 *
 * Until they are set, the site behaves exactly as it does now: no sign-in link
 * appears, and nothing breaks. See SUPABASE-SETUP.md.
 */

window.CODEX_SUPABASE = {
  url: 'YOUR_SUPABASE_PROJECT_URL',
  anonKey: 'YOUR_SUPABASE_ANON_KEY',
};

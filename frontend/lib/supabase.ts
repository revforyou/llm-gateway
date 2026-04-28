import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export const DEMO_TEAM_ID =
  process.env.NEXT_PUBLIC_DEMO_TEAM_ID ?? "00000000-0000-0000-0000-000000000001";

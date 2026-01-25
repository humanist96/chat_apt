import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

// Check if Supabase is properly configured
export const isSupabaseConfigured = Boolean(
  SUPABASE_URL &&
  SUPABASE_ANON_KEY &&
  !SUPABASE_URL.includes('your-project')
)

// Create a mock supabase client for development when not configured
const createMockClient = () => ({
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({
      data: { subscription: { unsubscribe: () => {} } },
    }),
    signUp: async () => ({ data: { user: null, session: null }, error: new Error('Supabase not configured') }),
    signInWithPassword: async () => ({ data: { user: null, session: null }, error: new Error('Supabase not configured') }),
    signInWithOAuth: async () => ({ data: { url: null, provider: null }, error: new Error('Supabase not configured') }),
    signOut: async () => ({ error: null }),
    refreshSession: async () => ({ data: { session: null, user: null }, error: null }),
  },
  from: () => ({
    select: () => ({
      eq: () => ({
        single: async () => ({ data: null, error: new Error('Supabase not configured') }),
      }),
    }),
    insert: async () => ({ data: null, error: new Error('Supabase not configured') }),
    update: () => ({
      eq: async () => ({ data: null, error: new Error('Supabase not configured') }),
    }),
  }),
})

export const supabase = isSupabaseConfigured
  ? createClientComponentClient()
  : (createMockClient() as any)

'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from 'react'
import { User, Session } from '@supabase/supabase-js'
import { supabase, isSupabaseConfigured } from '@/lib/supabase'
import { api } from '@/lib/api'

interface UserProfile {
  id: string
  email: string
  name: string | null
  membership_tier: 'free' | 'basic' | 'premium'
  avatar_url: string | null
  created_at: string
}

interface AuthState {
  user: User | null
  profile: UserProfile | null
  session: Session | null
  isAuthenticated: boolean
  isLoading: boolean
}

interface AuthContextType extends AuthState {
  signUp: (email: string, password: string, name?: string) => Promise<void>
  signIn: (email: string, password: string) => Promise<void>
  signInWithGoogle: () => Promise<void>
  signInWithKakao: () => Promise<void>
  signInWithNaver: () => Promise<void>
  signOut: () => Promise<void>
  updateProfile: (data: Partial<UserProfile>) => Promise<void>
  refreshSession: () => Promise<void>
  isConfigured: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    profile: null,
    session: null,
    isAuthenticated: false,
    isLoading: true,
  })

  const fetchProfile = useCallback(async (userId: string): Promise<UserProfile | null> => {
    try {
      const { data, error } = await supabase
        .from('user_profiles')
        .select('*')
        .eq('id', userId)
        .single()

      if (error) {
        console.error('Error fetching profile:', error)
        return null
      }

      return data
    } catch (error) {
      console.error('Error fetching profile:', error)
      return null
    }
  }, [])

  const setSession = useCallback(
    async (session: Session | null) => {
      if (session?.user) {
        const profile = await fetchProfile(session.user.id)
        api.setToken(session.access_token)
        setState({
          user: session.user,
          profile,
          session,
          isAuthenticated: true,
          isLoading: false,
        })
      } else {
        api.setToken(null)
        setState({
          user: null,
          profile: null,
          session: null,
          isAuthenticated: false,
          isLoading: false,
        })
      }
    },
    [fetchProfile]
  )

  useEffect(() => {
    const initAuth = async () => {
      if (!isSupabaseConfigured) {
        setState((prev) => ({ ...prev, isLoading: false }))
        return
      }

      try {
        const {
          data: { session },
        } = await supabase.auth.getSession()
        await setSession(session)
      } catch (error) {
        console.error('Error initializing auth:', error)
        setState((prev) => ({ ...prev, isLoading: false }))
      }
    }

    initAuth()

    if (!isSupabaseConfigured) return

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event: any, session: Session | null) => {
      await setSession(session)
    })

    return () => subscription.unsubscribe()
  }, [setSession])

  const signUp = async (email: string, password: string, name?: string) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { name },
      },
    })

    if (error) throw error

    if (data.user) {
      await supabase.from('user_profiles').insert({
        id: data.user.id,
        email: data.user.email,
        name: name || null,
        membership_tier: 'free',
      })
    }
  }

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (error) throw error
  }

  const signInWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })

    if (error) throw error
  }

  const signInWithKakao = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'kakao',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })

    if (error) throw error
  }

  const signInWithNaver = async () => {
    // Naver OAuth is not directly supported by Supabase
    // Using custom OAuth flow with Naver's provider
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'naver' as any,
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    })

    if (error) throw error
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  const updateProfile = async (data: Partial<UserProfile>) => {
    if (!state.user) throw new Error('Not authenticated')

    const { error } = await supabase
      .from('user_profiles')
      .update(data)
      .eq('id', state.user.id)

    if (error) throw error

    setState((prev) => ({
      ...prev,
      profile: prev.profile ? { ...prev.profile, ...data } : null,
    }))
  }

  const refreshSession = async () => {
    const { data, error } = await supabase.auth.refreshSession()
    if (error) throw error
    await setSession(data.session)
  }

  return (
    <AuthContext.Provider
      value={{
        ...state,
        signUp,
        signIn,
        signInWithGoogle,
        signInWithKakao,
        signInWithNaver,
        signOut,
        updateProfile,
        refreshSession,
        isConfigured: isSupabaseConfigured,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export function useRequireAuth() {
  const auth = useAuth()

  useEffect(() => {
    if (!auth.isLoading && !auth.isAuthenticated) {
      window.location.href = '/login'
    }
  }, [auth.isLoading, auth.isAuthenticated])

  return auth
}

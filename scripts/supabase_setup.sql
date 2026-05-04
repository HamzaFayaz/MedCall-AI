-- SQL Setup Script for Supabase
-- Copy and paste this into the Supabase SQL Editor to create the necessary tables.
-- If you already have tables created, scroll to the BOTTOM for ALTER TABLE statements.

-- ============================================================
-- SECTION 1: CREATE TABLES (Run for a fresh setup)
-- ============================================================

-- 1. Doctors Table
CREATE TABLE IF NOT EXISTS public.doctors (
    id UUID PRIMARY KEY,
    npi VARCHAR UNIQUE NOT NULL,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    prefix VARCHAR,
    specialty VARCHAR NOT NULL,
    email VARCHAR,
    phone VARCHAR,
    gender VARCHAR,
    active BOOLEAN DEFAULT TRUE,
    -- Hospital-specific metadata (from Mercy General doctor directory)
    focus TEXT,
    experience_years INT,
    room VARCHAR,
    extension VARCHAR,
    booking_status VARCHAR,
    -- Complete raw FHIR Practitioner JSON for full fidelity
    raw_fhir_data JSONB
);

-- 2. Patients Table
CREATE TABLE IF NOT EXISTS public.patients (
    id UUID PRIMARY KEY,
    mrn VARCHAR UNIQUE,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    dob DATE NOT NULL,
    gender VARCHAR,
    phone VARCHAR NOT NULL,
    address_line VARCHAR,
    city VARCHAR,
    state VARCHAR,
    postal_code VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Medical Profiles Table
-- Stores the optimized, token-efficient clinical summary for each patient.
-- The clinical_data JSONB column follows the patient_profile_template.md schema.
CREATE TABLE IF NOT EXISTS public.medical_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES public.patients(id) ON DELETE CASCADE,
    clinical_data JSONB NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Appointments Table
CREATE TABLE IF NOT EXISTS public.appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES public.patients(id) ON DELETE CASCADE,
    doctor_id UUID REFERENCES public.doctors(id) ON DELETE CASCADE,
    appointment_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'scheduled',
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ============================================================
-- SECTION 2: ALTER TABLE (Run ONLY if tables already exist)
-- ============================================================
-- These statements add the new columns to your existing tables.
-- They are safe to run — IF NOT EXISTS prevents errors on re-run.

ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS focus TEXT;
ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS experience_years INT;
ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS room VARCHAR;
ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS extension VARCHAR;
ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS booking_status VARCHAR;
ALTER TABLE public.doctors ADD COLUMN IF NOT EXISTS raw_fhir_data JSONB;

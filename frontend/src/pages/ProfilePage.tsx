/**
 * Body profile.
 *
 * The profile drives workout and diet generation, so the form validates before
 * submitting and reports field-level errors, per frontend rules section 8.
 */

import { useEffect, useState, type FormEvent } from "react";

import {
  Button,
  Card,
  ErrorState,
  Field,
  LoadingState,
  PageHeader,
  SelectField,
  StatTile,
} from "@/components/ui";
import { useProfile, useSaveProfile } from "@/hooks/queries";
import { ApiError } from "@/services/api/client";
import type { FitnessGoal, FitnessLevel, Gender, ProfileInput } from "@/types/api";

const GENDERS: Gender[] = ["Male", "Female", "Other", "Prefer not to say"];
const GOALS: FitnessGoal[] = ["Weight Loss", "Muscle Gain", "General Fitness"];
const LEVELS: FitnessLevel[] = ["Beginner", "Intermediate", "Advanced"];

interface FormState {
  age: string;
  gender: Gender;
  heightCm: string;
  weightKg: string;
  fitnessGoal: FitnessGoal;
  fitnessLevel: FitnessLevel;
  workoutDurationMinutes: string;
  problemAreas: string;
}

const EMPTY_FORM: FormState = {
  age: "",
  gender: "Prefer not to say",
  heightCm: "",
  weightKg: "",
  fitnessGoal: "General Fitness",
  fitnessLevel: "Beginner",
  workoutDurationMinutes: "30",
  problemAreas: "",
};

/** Bounds mirror the backend's, so the user sees an error before a round trip. */
function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  const age = Number(form.age);
  const height = Number(form.heightCm);
  const weight = Number(form.weightKg);
  const duration = Number(form.workoutDurationMinutes);

  if (!form.age || age < 13 || age > 100) errors.age = "Enter an age between 13 and 100.";
  if (!form.heightCm || height <= 50 || height > 260)
    errors.heightCm = "Enter a height in centimetres.";
  if (!form.weightKg || weight <= 20 || weight > 400)
    errors.weightKg = "Enter a weight in kilograms.";
  if (duration < 5 || duration > 180)
    errors.workoutDurationMinutes = "Choose between 5 and 180 minutes.";

  return errors;
}

export default function ProfilePage() {
  const { data, isPending, isError, error, refetch } = useProfile();
  const save = useSaveProfile();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!data) return;
    setForm({
      age: String(data.age),
      gender: data.gender,
      heightCm: String(data.heightCm),
      weightKg: String(data.weightKg),
      fitnessGoal: data.fitnessGoal,
      fitnessLevel: data.fitnessLevel,
      workoutDurationMinutes: String(data.workoutDurationMinutes),
      problemAreas: data.problemAreas.join(", "),
    });
  }, [data]);

  const isMissing = error instanceof ApiError && error.status === 404;

  if (isPending) return <LoadingState label="Loading your profile" />;
  if (isError && !isMissing) {
    return (
      <ErrorState
        message="We could not load your profile."
        onRetry={() => void refetch()}
      />
    );
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    const payload: ProfileInput = {
      age: Number(form.age),
      gender: form.gender,
      heightCm: Number(form.heightCm),
      weightKg: Number(form.weightKg),
      fitnessGoal: form.fitnessGoal,
      fitnessLevel: form.fitnessLevel,
      workoutDurationMinutes: Number(form.workoutDurationMinutes),
      problemAreas: form.problemAreas
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    };

    save.mutate(payload, { onSuccess: () => setSaved(true) });
  }

  return (
    <>
      <PageHeader
        title="Your profile"
        subtitle="GymVision uses this to build workouts and meals that suit you."
      />

      {data && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile label="BMI" value={data.bmi} />
          <StatTile label="Goal" value={data.fitnessGoal} />
          <StatTile label="Level" value={data.fitnessLevel} />
          <StatTile label="Session" value={`${data.workoutDurationMinutes}m`} />
        </div>
      )}

      <Card>
        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Age"
              type="number"
              inputMode="numeric"
              value={form.age}
              error={errors.age}
              onChange={(event) => update("age", event.target.value)}
            />
            <SelectField
              label="Gender"
              value={form.gender}
              options={GENDERS}
              onChange={(value) => update("gender", value as Gender)}
            />
            <Field
              label="Height (cm)"
              type="number"
              inputMode="decimal"
              value={form.heightCm}
              error={errors.heightCm}
              onChange={(event) => update("heightCm", event.target.value)}
            />
            <Field
              label="Weight (kg)"
              type="number"
              inputMode="decimal"
              value={form.weightKg}
              error={errors.weightKg}
              onChange={(event) => update("weightKg", event.target.value)}
            />
            <SelectField
              label="Goal"
              value={form.fitnessGoal}
              options={GOALS}
              onChange={(value) => update("fitnessGoal", value as FitnessGoal)}
            />
            <SelectField
              label="Experience"
              value={form.fitnessLevel}
              options={LEVELS}
              onChange={(value) => update("fitnessLevel", value as FitnessLevel)}
            />
            <Field
              label="Time per session (minutes)"
              type="number"
              inputMode="numeric"
              value={form.workoutDurationMinutes}
              error={errors.workoutDurationMinutes}
              onChange={(event) =>
                update("workoutDurationMinutes", event.target.value)
              }
            />
            <Field
              label="Focus areas"
              placeholder="belly, arms"
              hint="Comma separated, optional"
              value={form.problemAreas}
              onChange={(event) => update("problemAreas", event.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Button type="submit" loading={save.isPending}>
              {data ? "Save changes" : "Create profile"}
            </Button>
            {saved && (
              <p role="status" className="text-sm text-positive">
                Profile saved.
              </p>
            )}
            {save.isError && (
              <p role="alert" className="text-sm text-danger">
                {save.error instanceof ApiError
                  ? save.error.message
                  : "We could not save your profile."}
              </p>
            )}
          </div>
        </form>
      </Card>
    </>
  );
}

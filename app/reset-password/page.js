import ResetPasswordForm from "./ResetPasswordForm";

export default async function ResetPasswordPage({ searchParams }) {
  const params = await searchParams;
  return (
    <ResetPasswordForm
      uid={typeof params?.uid === "string" ? params.uid : ""}
      token={typeof params?.token === "string" ? params.token : ""}
    />
  );
}

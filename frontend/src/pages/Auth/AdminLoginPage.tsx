import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2, Shield } from "lucide-react";
import { useAuth, getErrorMessage } from "@/contexts/AuthContext";
import { Button } from "@/components/common/Button";
import { Input } from "@/components/common/Input";
import { Label } from "@/components/common/Label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/common/Card";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

function isAdminPortalUser(user: {
  role?: string | null;
  roles: { name: string }[];
}): boolean {
  const names = new Set(user.roles.map((r) => r.name));
  return (
    names.has("admin") ||
    names.has("manager") ||
    user.role === "admin" ||
    user.role === "manager"
  );
}

export function AdminLoginPage() {
  const { login, logout } = useAuth();
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setIsSubmitting(true);
    try {
      const user = await login(data.email, data.password);
      if (!isAdminPortalUser(user)) {
        await logout();
        toast.error("This account cannot access the Admin Portal. Use User Login.");
        return;
      }
      toast.success("Welcome to Admin Center");
      navigate("/admin");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="border-border/60 shadow-xl">
      <CardHeader className="space-y-1">
        <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
          <Shield className="h-5 w-5" />
        </div>
        <CardTitle className="font-display text-2xl">Admin Sign in</CardTitle>
        <CardDescription>
          Administrators and managers only — Microsoft 365–style Admin Center
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="admin-email">Work email</Label>
            <Input
              id="admin-email"
              type="email"
              placeholder="admin@company.com"
              autoComplete="email"
              {...register("email")}
            />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="admin-password">Password</Label>
            <Input
              id="admin-password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="animate-spin" />}
            Sign in to Admin
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Looking for the AI assistant?{" "}
            <Link to="/login" className="text-primary hover:underline">
              User login
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

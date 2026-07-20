/**
 * ShadCN-style UI barrel — design system primitives.
 * Existing `components/common/*` remain the source of truth for Button/Card/etc.
 * New redesign sections should prefer `@/components/ui` imports.
 */

export { Button, buttonVariants } from "@/components/common/Button";
export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/common/Card";
export { Input } from "@/components/common/Input";
export { Label } from "@/components/common/Label";
export { Badge } from "@/components/common/Badge";
export { Modal } from "@/components/common/Modal";
export { Avatar } from "@/components/common/Avatar";
export { Checkbox } from "@/components/common/Checkbox";
export { Loader, PageLoader } from "@/components/common/Loader";
export { EmptyState } from "@/components/common/EmptyState";
export { ErrorState } from "@/components/common/ErrorState";
export { Skeleton, PageSkeleton, TableSkeleton } from "@/components/ui/skeleton";
export {
  PageTransition,
  Stagger,
  StaggerItem,
  MotionCard,
} from "@/components/ui/motion";

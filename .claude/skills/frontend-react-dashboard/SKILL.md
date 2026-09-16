---
name: frontend-react-dashboard
description: >
  Quy ước UI dashboard FlagOps — React 18 + TS + Vite + Tailwind + shadcn/ui.
  Nạp khi làm bất kỳ màn hình frontend nào.
---

# Quy ước Frontend Dashboard FlagOps

## 1. Cấu trúc thư mục

```
frontend/src/
├── pages/                  # Route-level components
│   ├── LoginPage.tsx
│   ├── ProjectsPage.tsx
│   ├── FlagListPage.tsx
│   ├── FlagDetailPage.tsx
│   ├── SegmentListPage.tsx
│   ├── ConfigNamespacePage.tsx
│   ├── AuditLogPage.tsx
│   └── FlagHealthPage.tsx
├── features/               # Feature-specific logic & components
│   ├── flags/
│   │   ├── components/     # FlagCard, FlagToggle, RuleBuilder...
│   │   ├── hooks/          # useFlags, useFlagDetail...
│   │   └── api.ts          # API calls cho flags
│   ├── config/
│   ├── segments/
│   ├── audit/
│   └── auth/
├── components/             # Shared UI components
│   ├── ui/                 # shadcn/ui components
│   ├── Layout.tsx
│   ├── Sidebar.tsx
│   └── ErrorBoundary.tsx
├── lib/
│   ├── api-client.ts       # Axios/fetch wrapper
│   ├── auth.ts             # JWT management
│   ├── constants.ts
│   └── utils.ts
├── hooks/                  # Shared hooks
└── types/                  # TypeScript types
```

## 2. TanStack Query cho server state — KHÔNG useEffect+fetch

### Ví dụ ĐÚNG:
```typescript
// features/flags/hooks/useFlags.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { flagApi } from "../api";

export function useFlags(projectId: string) {
  return useQuery({
    queryKey: ["flags", projectId],
    queryFn: () => flagApi.listFlags(projectId),
    staleTime: 30_000,
  });
}

export function useToggleFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: flagApi.toggleFlag,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["flags"] });
    },
  });
}
```

### Ví dụ SAI:
```typescript
// ❌ useEffect + fetch thủ công — CẤM
function FlagList({ projectId }: Props) {
  const [flags, setFlags] = useState<Flag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    fetch(`/api/v1/projects/${projectId}/flags`)  // CẤM
      .then(res => res.json())
      .then(setFlags)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [projectId]);
  // CẤM — dùng TanStack Query
}
```

## 3. React Hook Form + Zod cho form

### Ví dụ ĐÚNG:
```typescript
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const flagSchema = z.object({
  key: z.string().min(1).max(160).regex(/^[a-zA-Z0-9._-]+$/,
    "Key chỉ chấp nhận chữ cái, số, dấu chấm, gạch ngang, gạch dưới"),
  name: z.string().min(1).max(200),
  type: z.enum(["BOOLEAN", "STRING", "NUMBER", "JSON"]),
  is_client_visible: z.boolean().default(false),
  is_temporary: z.boolean().default(true),
});

function CreateFlagForm() {
  const form = useForm<z.infer<typeof flagSchema>>({
    resolver: zodResolver(flagSchema),
  });
  // ...
}
```

### Ví dụ SAI:
```typescript
// ❌ State thủ công cho mỗi field — CẤM
const [key, setKey] = useState("");
const [name, setName] = useState("");
const [type, setType] = useState("BOOLEAN");
// Validate thủ công bằng if/else — CẤM, dùng Zod
```

## 4. Design Token — Khai báo MỘT CHỖ

Tất cả giá trị thiết kế (màu, spacing, radius, font) khai báo trong Tailwind config
hoặc CSS variables. KHÔNG hardcode trong component.

### Ví dụ ĐÚNG:
```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        flagops: {
          primary: "#6366f1",
          success: "#22c55e",  // Flag ON
          danger: "#ef4444",   // Flag OFF
          warning: "#f59e0b",
          muted: "#94a3b8",
        },
      },
    },
  },
};

// Component dùng token
<Badge className="bg-flagops-success">ON</Badge>
```

### Ví dụ SAI:
```typescript
// ❌ Hardcode màu trong component — CẤM
<Badge style={{ backgroundColor: "#22c55e" }}>ON</Badge>
<div className="bg-[#6366f1]">...</div>  // Arbitrary value, CẤM
```

## 5. Component < 200 dòng thì tách

Nếu một component vượt 200 dòng, PHẢI tách thành các component con.

```
FlagDetailPage.tsx (orchestrator)
├── FlagHeader.tsx (tên, tag, toggle)
├── FlagVariations.tsx (danh sách variation)
├── RuleBuilder.tsx (trình soạn rule)
│   ├── RuleCard.tsx
│   ├── ConditionRow.tsx
│   └── DistributionSlider.tsx
└── EvaluationSimulator.tsx
```

## 6. CẤM business logic ở frontend

Frontend KHÔNG được:
- Đánh giá flag (evaluate)
- Tính diff giữa hai config release
- Tính debt score cho flag
- Tính phân bố bucketing
- Validate điều kiện targeting phức tạp

TẤT CẢ logic trên phải gọi API backend.

### Ví dụ ĐÚNG:
```typescript
// Mô phỏng đánh giá — GỌI API
const { mutate: simulate } = useMutation({
  mutationFn: (context: EvalContext) =>
    api.post(`/flags/${flagId}/environments/${envId}/simulate`, { context }),
});
```

### Ví dụ SAI:
```typescript
// ❌ Đánh giá flag ở frontend — CẤM
function evaluateFlag(rules: Rule[], context: Context) {
  for (const rule of rules) {
    if (matchConditions(rule.conditions, context)) {
      return rule.variation;  // CẤM — logic này phải ở backend engine
    }
  }
}
```

## 7. Trạng thái bắt buộc cho mọi bảng/danh sách

Mỗi component hiển thị dữ liệu PHẢI xử lý đủ 3 trạng thái:

```typescript
function FlagTable({ projectId }: Props) {
  const { data, isLoading, isError, error } = useFlags(projectId);

  if (isLoading) return <TableSkeleton rows={5} />;       // Loading state
  if (isError) return <ErrorAlert error={error} />;        // Error state
  if (!data?.length) return <EmptyState                     // Empty state
    icon={<FlagIcon />}
    title="Chưa có flag nào"
    action={<CreateFlagButton />}
  />;

  return <Table>...</Table>;
}
```

### Ví dụ SAI:
```typescript
// ❌ Không xử lý loading và error — CẤM
function FlagTable({ projectId }: Props) {
  const { data } = useFlags(projectId);
  return <Table>{data?.map(...)}</Table>;  // Không loading, không error, không empty
}
```

## 8. Danh sách màn hình chính (từ kế hoạch)

| Màn hình | Route | Sprint |
|----------|-------|--------|
| Login/Register | `/login`, `/register` | 1 |
| Danh sách project | `/projects` | 1 |
| Danh sách flag | `/projects/:p/flags` | 2 |
| Chi tiết flag + toggle | `/flags/:f` | 2 |
| Rule builder | `/flags/:f/env/:e/rules` | 3 |
| Mô phỏng đánh giá | `/flags/:f/env/:e/simulate` | 3 |
| Quản lý segment | `/projects/:p/segments` | 3 |
| Config namespace | `/env/:e/config` | 4 |
| Config diff + rollback | `/namespaces/:n/releases` | 4 |
| Audit log | `/env/:e/audit` | 1 |
| Flag health dashboard | `/projects/:p/flag-health` | 6 |
| Change request | `/env/:e/change-requests` | 6 |

## 9. Checklist tự kiểm tra

- [ ] Dùng TanStack Query, không useEffect+fetch
- [ ] Form dùng React Hook Form + Zod
- [ ] Màu sắc dùng design token, không hardcode
- [ ] Component < 200 dòng (tách nếu vượt)
- [ ] Không có business logic ở frontend
- [ ] Mọi bảng/danh sách có loading, error, empty state
- [ ] File nằm đúng thư mục (pages/, features/, components/)
- [ ] TypeScript strict, không dùng `any`

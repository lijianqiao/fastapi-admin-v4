/** 分页组件

 * 提供页码导航和每页条数选择。
 */

import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from "@/lib/icons"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PAGE_SIZE_OPTIONS } from "@/lib/constants"

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div className="flex flex-col items-center justify-between gap-4 py-4 sm:flex-row">
      <div className="text-sm text-muted-foreground">
        共 {total} 条，显示 {start}-{end}
      </div>

      <div className="flex items-center gap-4">
        {/* 每页条数 */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">每页</span>
          <Select
            value={String(pageSize)}
            onValueChange={(val) => onPageSizeChange(Number(val))}
          >
            <SelectTrigger className="h-8 w-[70px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZE_OPTIONS.map((size) => (
                <SelectItem key={size} value={String(size)}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* 页码导航 */}
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => onPageChange(1)}
            disabled={page <= 1}
          >
            <ChevronsLeftIcon className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeftIcon className="size-4" />
          </Button>
          <span className="px-3 text-sm font-medium">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
          >
            <ChevronRightIcon className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => onPageChange(totalPages)}
            disabled={page >= totalPages}
          >
            <ChevronsRightIcon className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

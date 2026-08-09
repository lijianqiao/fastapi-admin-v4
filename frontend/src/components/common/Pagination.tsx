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
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PAGE_SIZE_OPTIONS } from "@/lib/constants"

/** base-ui 的 Select 需要 items 才能在受控赋值时渲染选中项文案 */
const PAGE_SIZE_ITEMS = PAGE_SIZE_OPTIONS.map((size) => ({
  label: String(size),
  value: String(size),
}))

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
            items={PAGE_SIZE_ITEMS}
            value={String(pageSize)}
            onValueChange={(value) => {
              if (value !== null) onPageSizeChange(Number(value))
            }}
          >
            <SelectTrigger size="sm" className="w-[70px]" aria-label="每页条数">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {PAGE_SIZE_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>

        {/* 页码导航 */}
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="第一页"
            onClick={() => onPageChange(1)}
            disabled={page <= 1}
          >
            <ChevronsLeftIcon />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="上一页"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeftIcon />
          </Button>
          <span className="px-3 text-sm font-medium">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="下一页"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
          >
            <ChevronRightIcon />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="最后一页"
            onClick={() => onPageChange(totalPages)}
            disabled={page >= totalPages}
          >
            <ChevronsRightIcon />
          </Button>
        </div>
      </div>
    </div>
  )
}

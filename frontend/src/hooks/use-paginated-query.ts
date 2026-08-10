/** 分页查询 hook

 * 封装列表页共用的 page/pageSize/total/isLoading 状态与数据获取逻辑，
 * 筛选条件变化时由调用方决定是否需要重置 page（通常配合调用 setPage(1)）。
 */

import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import api from "@/lib/api"

interface UsePaginatedQueryOptions {
  url: string
  params?: Record<string, unknown>
  initialPageSize?: number
  errorMessage?: string
}

export function usePaginatedQuery<T>({
  url,
  params = {},
  initialPageSize = 10,
  errorMessage = "获取数据失败",
}: UsePaginatedQueryOptions) {
  const [items, setItems] = useState<T[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(initialPageSize)
  const [isLoading, setIsLoading] = useState(true)

  const paramsKey = JSON.stringify(params)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await api.get(url, {
        params: { ...(JSON.parse(paramsKey) as Record<string, unknown>), page, page_size: pageSize },
      })
      setItems(response.data?.data?.items ?? [])
      setTotal(response.data?.data?.total ?? 0)
    } catch {
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }, [url, page, pageSize, paramsKey, errorMessage])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handlePageSizeChange = useCallback((size: number) => {
    setPageSize(size)
    setPage(1)
  }, [])

  return {
    items,
    total,
    page,
    setPage,
    pageSize,
    isLoading,
    onPageSizeChange: handlePageSizeChange,
    refetch: fetchData,
  }
}

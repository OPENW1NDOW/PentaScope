'use client'

import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useState, useMemo } from 'react'
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'

interface SortableTableProps {
  data: Array<Record<string, unknown>>
  columns: Array<{
    key: string
    label: string
    sortable?: boolean
  }>
}

export function SortableTable({ data, columns }: SortableTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])

  const columnDefs = useMemo<ColumnDef<Record<string, unknown>>[]>(
    () =>
      columns.map((col) => ({
        accessorKey: col.key,
        header: col.label,
        enableSorting: col.sortable !== false,
        cell: (info) => {
          const val = info.getValue()
          if (val == null || val === '') return '—'
          return String(val)
        },
      })),
    [columns]
  )

  const table = useReactTable({
    data,
    columns: columnDefs,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (data.length === 0) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-8 text-center">
        <p className="text-[13px] text-[var(--text-tertiary)]">暂无数据</p>
      </div>
    )
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort()
                  return (
                    <th
                      key={header.id}
                      className={`text-left font-medium text-[var(--text-secondary)] px-3 py-2 border-b border-[var(--border)] bg-[var(--bg-page)] text-[12px] uppercase tracking-wider ${canSort ? 'cursor-pointer select-none hover:bg-[var(--bg-hover)]' : ''}`}
                      onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {canSort && (
                          header.column.getIsSorted() === 'asc' ? (
                            <ArrowUp size={12} className="text-[var(--text-tertiary)]" />
                          ) : header.column.getIsSorted() === 'desc' ? (
                            <ArrowDown size={12} className="text-[var(--text-tertiary)]" />
                          ) : (
                            <ArrowUpDown size={12} className="text-[var(--text-tertiary)] opacity-40" />
                          )
                        )}
                      </span>
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-[var(--bg-hover)] transition-colors">
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="px-3 py-2 border-b border-[var(--divider)] text-[var(--text-primary)]"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

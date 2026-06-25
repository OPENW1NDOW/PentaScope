'use client'

import type { ScenarioPayload as ScenarioPayloadType, Scenario } from '@/types'
import type {
  S1FeatureIterationPayload,
  S2MarketEntryPayload,
  S3PricingStrategyPayload,
  S4MonitoringPayload,
  S5PositioningPayload,
} from '@/types'
import { SCENARIO_LABELS } from '@/types'
import { S1Payload } from './s1/S1Payload'
import { S2Payload } from './s2/S2Payload'
import { S3Payload } from './s3/S3Payload'
import { S4Payload } from './s4/S4Payload'
import { S5Payload } from './s5/S5Payload'

interface ScenarioPayloadProps {
  payload: ScenarioPayloadType
  scenario: Scenario
}

export function ScenarioPayload({ payload, scenario }: ScenarioPayloadProps) {
  const label = SCENARIO_LABELS[scenario] ?? scenario

  const renderPayload = () => {
    switch (scenario) {
      case 'S1':
        return <S1Payload payload={payload as S1FeatureIterationPayload} />
      case 'S2':
        return <S2Payload payload={payload as S2MarketEntryPayload} />
      case 'S3':
        return <S3Payload payload={payload as S3PricingStrategyPayload} />
      case 'S4':
        return <S4Payload payload={payload as S4MonitoringPayload} />
      case 'S5':
        return <S5Payload payload={payload as S5PositioningPayload} />
      default:
        return (
          <p className="text-[13px] text-[var(--text-tertiary)]">
            未知场景类型：{scenario}
          </p>
        )
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        {label} — 场景专有分析
      </h3>
      {renderPayload()}
    </div>
  )
}

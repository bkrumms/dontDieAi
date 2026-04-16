# Recurring Schemas

These shapes appear across many endpoints in the OpenAPI spec.

## Player state
```ts
{
  timeCrystal: number,
  originalHealth: number,
  health: number,
  maxHealth: number,
  trinkets: Trinket[],
  statusEffects: StatusEffect[],
  isResurrected: boolean,
  dice: Dice[],
  boosts: Boost[],           // food
  points: number,
  pointDetails: ...,
  atkCount: number,
  damageMultiplier: number,
  pointsMultiplier: number
}
```

## Dice
```ts
{
  order: number,
  ability: Ability[],        // the Sides
  id: string
}
```

## Ability (a Side)
```ts
{
  id: string,
  tags: string[],
  uuid: string,
  asset: string,
  label: string,
  exhaust: boolean,          // one-time use per battle
  sideType: "Attack" | "Tactic" | "Power",
  exhausted: boolean,        // current exhausted state
  specialEffect: ...,
  damage: number,
  block: number,
  heal: number,
  poison: number,
  bleed: number
}
```

## Monster
```ts
{
  id: string,
  name: string,
  maxHealth: number,
  health: number,
  ability: Ability[],
  statusEffects: StatusEffect[],
  uuid: string,
  tags: string[],
  image: string,
  description: string,
  defendBoostBonus: number,
  abilityCycleFromIndex: number
}
```

## Movement state
```ts
{
  activePath: string,
  currentIndex: number,
  rolledSteps: number | null,
  pendingChoice: ...,
  inState: string,
  justRejoinedFromFork: boolean | null
}
```

## Response envelope
Every response: `{ success: boolean, data: <payload> }`. Errors: `400` (System Error), `404` (Not Found).

<script setup>
const props = defineProps(["store"]);

function take(n) {
  if (props.store.game) props.store.game.sendAction("take", { n });
}
</script>

<template>
  <div style="font-family: system-ui, sans-serif; padding: 2rem; text-align: center;">
    <div v-if="!store.snap">connecting…</div>
    <div v-else>
      <h1>Last Coin Loses</h1>
      <p style="font-size: 2rem; font-weight: 700;">Coins left: {{ store.snap.coins }}</p>

      <p v-if="store.snap.phase === 'finished'">
        {{ store.snap.winner === store.snap.your_seat ? "You win!" : "You lose." }}
      </p>

      <template v-else>
        <p>{{ store.snap.current_player === store.snap.your_seat ? "Your move." : "Opponent's move…" }}</p>
        <button
          :disabled="store.snap.current_player !== store.snap.your_seat || store.snap.coins < 1 || !store.game"
          @click="take(1)">Take 1</button>
        <button
          :disabled="store.snap.current_player !== store.snap.your_seat || store.snap.coins < 2 || !store.game"
          @click="take(2)">Take 2</button>
      </template>
    </div>
  </div>
</template>

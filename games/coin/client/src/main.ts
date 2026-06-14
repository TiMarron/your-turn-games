import { createApp, reactive } from "vue";
import App from "./App.vue";
// The platform SDK (copied from sdk/client.js). Plain JS — Vite resolves it.
import { connect } from "./sdk.js";

// A tiny reactive store the component reads; the SDK pushes state into it.
const store = reactive({ snap: null as any, game: null as any });

connect({ onState: (snap: any) => { store.snap = snap; } })
  .then((game) => { store.game = game; });

createApp(App, { store }).mount("#app");

import {BTable} from 'bootstrap-vue'
import URI from 'urijs'
import moment from 'moment'

import axios from 'hunter2/js/axios.js'

export default {
  components: {
    'b-table': BTable,
  },
  computed: {
    sortedPuzzles() {
      function comparePuzzles(a, b) {
        const ad = new Date(a.guesses[0].given)
        const bd = new Date(b.guesses[0].given)
        return bd - ad
      }
      return [...this.puzzles].sort(comparePuzzles)
    },
  },
  created: function() {
    this.updateData(true)
  },
  props: ['href'],
  data () {
    return {
      puzzles: [],
      solved_puzzles: [],
      'guess_fields': [
        'user',
        'guess',
        'given',
      ],
      'clue_fields': [
        'type',
        'text',
        'received_at',
      ],
    }
  },
  methods: {
    moment: moment,
    updateData: function(force) {
      clearTimeout(this.timer)
      if (force || this.autoUpdate) {
        let url = URI(this.href)
        let v = this
        axios.get(url).then(response => {
          v.puzzles = response.data.puzzles
          v.solved_puzzles = response.data.solved_puzzles
        })
        if (this.autoUpdate) {
          this.timer = setTimeout(this.updateData, 5000)
        }
      }
    },
  },
}

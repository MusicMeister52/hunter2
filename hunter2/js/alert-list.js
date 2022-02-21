import 'bootstrap/js/dist/alert'
import 'bootstrap/js/dist/button'

export default {
  methods: {
    announcementExists: function(announcementID) {
      return (announcementID in this.announcements)
    },
  },
  props: [
    'announcements',
    'messages',
  ],
}

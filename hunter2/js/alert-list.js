import {BAlert} from 'bootstrap-vue'

export default {
  components: {
    'b-alert': BAlert,
  },
  data: function() {
    return {
      announcements: {},
      messages: [],
    }
  },
  methods: {
    addAnnouncement: function(announcement) {
      announcement = {dismissible: false, ...announcement}
      this.$set(this.announcements, announcement.announcement_id, {
        text: announcement.message,
        title: announcement.title,
        variant: announcement.variant,
        dismissible: announcement.dismissible,
      })
    },
    deleteAnnouncement: function(announcement) {
      if (!(announcement.announcement_id in this.announcements)) {
        throw `Deleted invalid announcement: ${announcement.announcement_id}`
      }
      this.$delete(this.announcements, announcement.announcement_id)
    },
  },
}

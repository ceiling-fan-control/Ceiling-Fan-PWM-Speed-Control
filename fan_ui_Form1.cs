using System;
using System.Threading;
using System.IO.Ports;
using System.Windows.Forms;
using System.Xml;
using System.ServiceModel.Syndication;

namespace fan_controller_ui_window
{
    public partial class ui_form : Form
    {
        // Create the serial port with basic settings
        private SerialPort port = new SerialPort("COM3", 9600, Parity.None, 8, StopBits.One);
        private readonly Mutex m = new Mutex();

        public ui_form()
        {
            InitializeComponent();
            tempULabel.Text = "Temperature Unit";
            rbCels.Text = "Celsius";
            rbFahr.Text = "Fahrenheit";
            fanSpeedLabel.Text = "Fan Speed";
            fanSpeedBar.Value = 4;
            sendButton.Text = "Send";

            sendButton.Click += new System.EventHandler(this.send_click);
            rbCels.Click += new System.EventHandler(this.handle_rb_click);
            rbFahr.Click += new System.EventHandler(this.handle_rb_click);
            
            ThreadStart timer_start = new ThreadStart(timer_thread);
            Thread timer_child = new Thread(timer_start);
            timer_child.Start();

            ThreadStart rss_start = new ThreadStart(rss_thread);
            Thread rss_child = new Thread(rss_start);
            rss_child.Start();
        }

        public void timer_thread()
        {
            while (true)
            {
                m.WaitOne();
                var current_time = get_time();
                Console.WriteLine(current_time + "");
                send_serial_data(current_time + "", '%');
                m.ReleaseMutex();
                Thread.Sleep(60000);
            }
        }

        public void rss_thread()
        {
            while (true)
            {
                //string url = "http://feeds.bbci.co.uk/news/world/rss.xml";
                string url = "https://www.npr.org/rss/rss.php?id=1004";
                XmlReader reader = XmlReader.Create(url);
                SyndicationFeed feed = SyndicationFeed.Load(reader);
                reader.Close();
                foreach (SyndicationItem item in feed.Items)
                {
                    String subject = item.Title.Text;

                    m.WaitOne();
                    send_serial_data(subject, '#');
                    Console.Write("Writing subject: ");
                    Console.WriteLine(subject);
                    m.ReleaseMutex();
                    Thread.Sleep(3 * 60000);
                    // String summary = item.Summary.Text;
                }
            }
        }

        private void handle_rb_click(object sender, EventArgs e)
        {
            Console.WriteLine(sender.ToString());
            if (rbCels.Checked)
            {
                Console.WriteLine("cels is clicked");
                send_serial_data("C", '^');
            }
            else if (rbFahr.Checked)
            {
                Console.WriteLine("fahr is clicked");
                send_serial_data("F", '^');
            }
        }

        private string get_time()
        {
            return DateTime.Now.ToString("h:mm");
        }

        private void send_click(object sender, EventArgs e)
        {
            Console.WriteLine(fanSpeedBar.Value + "");
            send_serial_data(fanSpeedBar.Value + "", ';');
        }

        private void send_serial_data(String serial_data, char delim)
        {
            port.Open();
            port.Write("&" + serial_data + delim);
            port.Close();
        }
    }
}

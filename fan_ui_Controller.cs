using System;
using System.ComponentModel;
using System.IO.Ports;
using System.Linq;
using System.Management;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Threading;

namespace Automatic_Fan_Controller
{
    public  class Controller : INotifyPropertyChanged
    {
        private Thread? readThread;
        private readonly SerialPort _serialPort = new();
        private readonly DispatcherTimer _dataUpdaterTimer = new();
        private int _dataUpdaterTime = 0;

        private bool _isAutoMode = true;
        private bool _isManualMode = false;
        private bool _isSearchingPort = true;
        private bool _isPortFound = true;
        private bool _isConnected = false;
        private bool _isReady = false;
        private int _personCount = 0;
        private int _temperature = 0;
        private int _activationTemp = 25; // default
        private int _fanSpeed = 0;
        private int _startFanSpeed = 50; // default

        public Controller()
        {
            _dataUpdaterTimer.Tick += new EventHandler(DataUpdaterTimer_Tick);
            _dataUpdaterTimer.Interval = new TimeSpan(0, 0, 1);
        }

        public bool IsAutoMode
        {
            get { return _isAutoMode; }
            set 
            { 
                _isAutoMode = value;
                OnPropertyChanged("IsAutoMode");
                SendDataToArduino("Mode", 1); // 1 - auto mode
            }
        }

        public bool IsManualMode
        {
            get { return _isManualMode; }
            set
            {
                _isManualMode = value;
                OnPropertyChanged("IsManualMode");
                SendDataToArduino("Mode", 0); // 0 - manual mode
            }
        }

        public bool IsSearchingPort
        { 
            get { return _isSearchingPort; }
            set
            {
                _isSearchingPort = value;
                OnPropertyChanged("IsSearchingPort");
            }
        }

        public bool IsPortFound
        {
            get { return _isPortFound; }
            set
            {
                _isPortFound = value;
                OnPropertyChanged("IsPortFound");
            }
        }

        public bool IsConnected
        {
            get { return _isConnected; }
            set
            {
                _isConnected = value;
                OnPropertyChanged("IsConnected");

                readThread = new Thread(new ThreadStart(ReadSerialPortData));
                readThread.Start();
            }
        }

        public bool IsReady
        {
            get { return _isReady; }
            set
            {
                _isReady = value;
                OnPropertyChanged("IsReady");
            }
        }

        public int PersonCount
        {
            get { return _personCount; }
            set 
            { 
                _personCount = value;
                OnPropertyChanged("PersonCount");
            }
        }

        public int Temperature
        {
            get { return _temperature; }
            set 
            {
                _temperature = value;
                OnPropertyChanged("Temperature");
            }
        }

        public int ActivationTemp
        {
            get { return _activationTemp; }
            set 
            { 
                if (value >= 10 && value <= 40) // default range
                {
                    _activationTemp = value;
                    OnPropertyChanged("ActivationTemp");
                    SendDataToArduino("ActivationTemp", value);
                }
            }
        }

        public int FanSpeed
        {
            get { return _fanSpeed; }
            set 
            {
                if (value >= 0 && value <= 100)
                {
                    _fanSpeed = value;
                    OnPropertyChanged("FanSpeed");

                    if (IsManualMode)
                    {
                        SendDataToArduino("FanSpeed", value);
                    }
                }
            }
        }

        public int StartFanSpeed
        { 
            get { return _startFanSpeed; }
            set 
            {
                if (value >= 20 && value <= 100) // default range
                {
                    _startFanSpeed = value;
                    OnPropertyChanged("StartFanSpeed");
                    SendDataToArduino("StartFanSpeed", value);
                }
            }
        }



        public async void ConnectArduinoPortAsync()
        {
            IsSearchingPort = true;
            await Task.Delay(5000);

            string? arduinoPort = GetArduinoPort();

            if (arduinoPort is not null)
            {
                try
                {
                    _serialPort.PortName = arduinoPort;
                    _serialPort.BaudRate = 115200;
                    _serialPort.Open();
                    _dataUpdaterTimer.Start();

                    IsPortFound = true;
                    IsConnected = true;
                    IsSearchingPort = false;
                    await Task.Delay(2000);
                    IsReady = true;
                }
                catch (UnauthorizedAccessException) { }
            }
            else
            {
                IsPortFound = false;
                IsConnected = false;
                IsSearchingPort = false;

                await Task.Delay(1000);
                ConnectArduinoPortAsync();
            }
        }

        private static string? GetArduinoPort()
        {
            ManagementScope connectionScope = new();
            SelectQuery serialQuery = new("SELECT * FROM Win32_SerialPort");
            ManagementObjectSearcher searcher = new(connectionScope, serialQuery);

            try
            {
                foreach (ManagementObject item in searcher.Get().Cast<ManagementObject>())
                {
                    string? desc = item["Description"].ToString();
                    string? deviceId = item["DeviceID"].ToString();

                    if (desc.Contains("Arduino"))
                    {
                        return deviceId;
                    }
                }
            }
            catch (ManagementException) { }

            return null;
        }

        private async void ReadSerialPortData()
        {
            while (_serialPort.IsOpen)
            {
                try
                {
                    if (_serialPort.BytesToRead > 0)
                    {
                        string serialData = _serialPort.ReadLine();

                        if (serialData.Length > 5)
                        {
                            ParseDataFromSerial(serialData);
                        }
                    }
                }
                catch (OperationCanceledException)
                {
                    IsConnected = false;
                    IsReady = false;

                    await Task.Delay(3000);
                    ConnectArduinoPortAsync();
                }
                catch (TimeoutException) { }
            }
        }

        private void ParseDataFromSerial(string serialData)
        {
            try
            {
                string dataType = serialData[..serialData.IndexOf(":")];
                int dataValue = int.Parse(serialData[(serialData.IndexOf(":") + 1)..]);

                switch (dataType)
                {
                    case "PersonCount":
                        PersonCount = dataValue;
                        break;

                    case "FanSpeed":
                        if (IsAutoMode) FanSpeed = dataValue;
                        break;

                    case "Temperature":
                        Temperature = dataValue;
                        break;
                }
            }
            catch { }
        }

        private void SendDataToArduino(string dataName, int dataValue)
        {
            if (_serialPort.IsOpen)
            {
                _serialPort.WriteLine($"{dataName}:{dataValue}");
            }
        }

        private void DataUpdaterTimer_Tick(object sender, EventArgs e)
        {
            _dataUpdaterTime++;
        }


        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged(string name)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
        }
    }
}
